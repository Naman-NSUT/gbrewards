"""Proof-of-purchase file storage.

The warranty stores an opaque object KEY, never a path or a URL, so the backing
store is a swap of this module rather than a change to any flow that uses it.
Local disk is the right first answer: proof files exist only for customer
self-registrations — by design a small number, since every one of them is a
dealer who failed to register — and are read only by an admin working the
approval queue. A disk mount is one fewer third-party credential in a system
that already holds customer PII.

These uploads arrive from ANONYMOUS callers, which sets every rule below:

  * Size is enforced while streaming. Content-Length is a number the client
    writes and is therefore not a limit.
  * The file type is decided by MAGIC BYTES. The declared content type is also
    client-written; it is checked first only so a wrong file gets a friendly
    error instead of a confusing one.
  * The stored name is a random key plus a whitelisted extension. Nothing the
    customer typed — filename, extension, content type — ever reaches the
    filesystem, so 'invoice.php' and '../../etc/passwd' are not expressible.
  * Files are written under a resolved root and every read path is re-checked
    against it, so a malformed key cannot escape the directory.
"""

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_CHUNK_BYTES = 64 * 1024

# Sniffed kind -> canonical extension. A format with no entry here cannot be
# stored at all, so this map is the whitelist rather than a hint.
_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "application/pdf": ".pdf",
}


# Extension -> content type, inverted from the whitelist above. A stored file is
# served back as exactly the kind it was SNIFFED as when it arrived, decided at
# the only moment we held the real bytes and a rule to judge them by. Re-sniffing
# on the way out, or trusting anything the uploader said, would let a file that
# passed validation once be served as something else later.
_CONTENT_TYPES = {extension: kind for kind, extension in _EXTENSIONS.items()}

# What a read can ever hand back, for the proof endpoint's OpenAPI. Derived from
# the whitelist rather than retyped beside it, so a format added or dropped here
# cannot leave the documented types describing a different set to the stored ones.
SERVED_CONTENT_TYPES: tuple[str, ...] = tuple(_EXTENSIONS)


@dataclass(frozen=True)
class StoredFile:
    key: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class LoadedFile:
    """A stored proof read back for an admin who has to look at it."""

    key: str
    content_type: str
    extension: str
    size_bytes: int
    data: bytes


def _root() -> Path:
    """Where uploads live.

    Prefers a `uploads_dir` setting if one is added to Settings later, then the
    UPLOADS_DIR environment variable, then a path inside the deployment — so
    this works today and picks up the config knob the moment it exists.
    """
    configured = str(getattr(settings, "uploads_dir", "") or os.environ.get("UPLOADS_DIR", ""))
    return Path(configured or "var/uploads").expanduser().resolve()


def _sniff(head: bytes) -> str | None:
    """Identify a file by its leading bytes, or None if we do not accept it."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    # ISO-BMFF container: what an iPhone camera roll hands over by default, and
    # therefore what a real customer photographing an invoice will send.
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"heim", b"mif1", b"msf1"):
        return "image/heic"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _remove(destination: Path) -> None:
    """Delete a half-written upload. Never raises, whatever the disk says.

    Every caller is inside an `except` block that is on its way to raising a
    friendly AppError. If the failure being handled was the mkdir itself, the
    parent is not a directory and unlink() answers with NotADirectoryError —
    raised from inside the handler, it REPLACES the friendly error with a bare
    500, so the customer whose upload we could not store is told "Internal
    server error" and has no reason to try again.
    """
    try:
        destination.unlink(missing_ok=True)
    except OSError as exc:  # noqa: BLE001 - cleanup must never mask the real error
        logger.warning("proof_cleanup_failed path=%s err=%s", destination, exc)


def save_upload(upload: UploadFile, *, prefix: str = "proofs") -> StoredFile:
    """Validate and store one uploaded file. Returns the key to persist.

    Raises AppError on anything the customer can fix (wrong type, too large,
    empty) so the form can show a usable message.
    """
    declared = (upload.content_type or "").split(";")[0].strip().lower()
    if not (declared.startswith("image/") or declared == "application/pdf"):
        raise AppError(
            "unsupported_file",
            400,
            "Upload a photo or a PDF of your invoice",
            {"content_type": declared or "unknown"},
        )

    head = upload.file.read(_CHUNK_BYTES)
    if not head:
        raise AppError("empty_file", 400, "That file is empty — please attach your invoice")

    kind = _sniff(head)
    if kind is None:
        raise AppError(
            "unsupported_file",
            400,
            "We could not read that file. Attach a JPG, PNG, HEIC or PDF of your invoice.",
        )

    key = f"{prefix}/{datetime.now(UTC):%Y/%m}/{uuid.uuid4().hex}{_EXTENSIONS[kind]}"
    destination = _root() / key

    size = 0
    try:
        # Inside the try, because this is the FIRST touch of the disk and so the
        # first place its problems surface: ENOSPC on a 5GB disk that holds only
        # ~1000 invoices at the 5MB cap, a volume that did not remount after an
        # incident, a mistyped UPLOADS_DIR. Outside the try those escape as a raw
        # OSError, which the error handler renders as internal_error / "Internal
        # server error" — no code the form can act on and nothing telling the
        # customer their invoice is worth resending.
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            chunk = head
            while chunk:
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise AppError(
                        "file_too_large",
                        413,
                        "That file is larger than 5 MB — send a smaller photo of the invoice",
                    )
                handle.write(chunk)
                chunk = upload.file.read(_CHUNK_BYTES)
        # Readable by the app user only: an invoice carries a name, an address
        # and a purchase, and nothing else on the box needs to read it.
        os.chmod(destination, 0o640)
    except AppError:
        _remove(destination)
        raise
    except OSError as exc:
        _remove(destination)
        logger.error("proof_upload_failed key=%s err=%s", key, exc)
        raise AppError(
            "upload_failed", 500, "We could not save that file, please try again"
        ) from exc

    return StoredFile(key=key, content_type=kind, size_bytes=size)


def path_for(key: str) -> Path:
    """Resolve a stored key to a path on disk, refusing anything outside the root.

    The keys this module generates are always safe; this guard exists because
    the key travels through the database and back, and a read endpoint must not
    trust a value merely because it round-tripped.
    """
    root = _root()
    candidate = (root / key).resolve()
    if not candidate.is_relative_to(root):
        raise AppError("invalid_file_key", 400, "Unknown file")
    return candidate


def load(key: str) -> LoadedFile:
    """Read a stored proof back, for the one screen allowed to look at it.

    Small files read whole rather than streamed: the cap is 5MB and the only
    caller is a human clicking one invoice at a time in the approval queue, so
    the complexity of a streaming response buys nothing.

    Two different 404s, because an approver must be able to tell them apart. A
    warranty with no key never had a proof; a key whose file is gone means the
    evidence was lost after the customer sent it. Collapsing the second into
    "no proof attached" would invite an approver to reject a genuine five-year
    warranty for a failure that is ours, not the customer's.
    """
    path = path_for(key)
    content_type = _CONTENT_TYPES.get(path.suffix.lower())
    if content_type is None:
        # The extension is minted from the whitelist at write time, so a key
        # that carries any other one did not come out of save_upload.
        raise AppError("invalid_file_key", 400, "Unknown file")

    try:
        data = path.read_bytes()
    except FileNotFoundError as exc:
        raise AppError(
            "proof_missing",
            404,
            "The invoice for this warranty is no longer in storage",
            {"key": key},
        ) from exc
    except OSError as exc:
        logger.error("proof_read_failed key=%s err=%s", key, exc)
        raise AppError(
            "proof_unreadable", 500, "We could not read that file, please try again"
        ) from exc

    return LoadedFile(
        key=key,
        content_type=content_type,
        extension=path.suffix.lower(),
        size_bytes=len(data),
        data=data,
    )


def discard(key: str | None) -> None:
    """Best-effort delete of a file whose owning transaction never completed.

    Never raises: an orphaned proof file is a housekeeping problem, while an
    exception here would mask the real failure the caller is already handling.
    """
    if not key:
        return
    try:
        path_for(key).unlink(missing_ok=True)
    except (AppError, OSError) as exc:  # noqa: BLE001 - cleanup must not raise
        logger.warning("proof_discard_failed key=%s err=%s", key, exc)
