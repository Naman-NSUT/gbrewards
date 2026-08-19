"""Allocation upload — the client's despatch file becomes the anti-abuse gate.

The allocation table decides which dealer may register which serial, so this
parser is a security boundary wearing a spreadsheet costume. Two properties
matter more than elegance:

  * RE-UPLOADING THE SAME FILE MUST BE SAFE. Despatch clerks re-send files, add
    ten rows to yesterday's export, and forward the same attachment twice. A row
    already allocated to the same dealer is a no-op SUCCESS. If a duplicate file
    were an error, the operator would learn to ignore the error report, and the
    error report is the whole value of this screen.
  * EVERY REJECTED LINE IS NAMED. "23 rows failed" cannot be acted on. Line 47
    with its serial and the reason can be fixed in five seconds.

Everything is validated against pre-fetched maps rather than a query per row: a
despatch file is thousands of lines, and a per-row SELECT turns a 3-second
upload into a 3-minute one.
"""

import csv
import io
import json
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.logging import get_logger
from app.dealer.models.allocation import Allocation, AllocationBatch
from app.dealer.models.dealer import Dealer
from app.dealer.models.unit import DealerUnit as Unit
from app.dealer.models.warranty import LIVE_STATUSES, Warranty
from app.dealer.services.audit import record_audit
from app.dealer.services.unitsource import normalise_serial

logger = get_logger(__name__)

# Column aliases. The client exports from their own despatch system and we do
# not control its headings; accepting the obvious variants is cheaper than
# telling a clerk to rename columns before every upload.
_SERIAL_KEYS = ("serial", "serial_no", "serial_number", "serialno", "unit_serial", "qr", "qr_code")
_DEALER_KEYS = ("dealer_code", "dealercode", "dealer", "code", "dealer_id")
_DISPATCH_KEYS = (
    "dispatch_ref", "dispatchref", "dispatch", "dispatch_no", "invoice", "invoice_ref",
)

# Rejections are stored on the batch row as JSON. Cap what we persist so one
# catastrophic file (wrong column entirely) cannot write a megabyte of text;
# the COUNT stays exact either way.
MAX_STORED_ERRORS = 500
# Guard the whole request: this endpoint reads the upload into memory.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class RowError:
    line: int
    serial: str | None
    dealer_code: str | None
    reason: str


@dataclass
class UploadResult:
    batch: AllocationBatch
    row_count: int = 0
    created_count: int = 0
    # Rows that were already allocated to the same dealer — a safe re-upload.
    unchanged_count: int = 0
    errors: list[RowError] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return self.created_count + self.unchanged_count

    @property
    def error_count(self) -> int:
        return len(self.errors)


def _decode(content: bytes) -> str:
    """Bytes to text, tolerating a BOM from Excel and Windows line endings."""
    if len(content) > MAX_UPLOAD_BYTES:
        raise AppError("file_too_large", 413, "The allocation file must be under 10 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel on a Windows machine still emits cp1252 for non-ASCII dealer
        # names. Falling back beats rejecting a file that is otherwise fine.
        text = content.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _header_map(fieldnames: Iterable[str | None]) -> dict[str, str]:
    """Map our canonical column names onto whatever the file actually calls them."""
    normalised = {
        (name or "").strip().lstrip("﻿").lower().replace(" ", "_"): name
        for name in fieldnames
        if name is not None
    }
    mapping: dict[str, str] = {}
    for canonical, aliases in (
        ("serial", _SERIAL_KEYS),
        ("dealer_code", _DEALER_KEYS),
        ("dispatch_ref", _DISPATCH_KEYS),
    ):
        for alias in aliases:
            if alias in normalised:
                mapping[canonical] = normalised[alias]
                break
    return mapping


def _chunked(values: list[str], size: int = 1000) -> Iterator[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


@dataclass(frozen=True)
class _ParsedRow:
    line: int
    serial: str
    dealer_code: str
    dispatch_ref: str | None


def _parse(text: str) -> tuple[list[_ParsedRow], list[RowError]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise AppError("empty_file", 400, "The file has no header row")

    columns = _header_map(reader.fieldnames)
    missing = [name for name in ("serial", "dealer_code") if name not in columns]
    if missing:
        raise AppError(
            "missing_columns",
            400,
            "The file must have 'serial' and 'dealer_code' columns",
            {"missing": missing, "found": [f for f in reader.fieldnames if f]},
        )

    rows: list[_ParsedRow] = []
    errors: list[RowError] = []
    for raw in reader:
        line = reader.line_num  # the line number the operator sees in Excel
        values = {key: (raw.get(column) or "").strip() for key, column in columns.items()}
        if not any(values.values()):
            continue  # blank line, including the trailing newline every file has

        serial = normalise_serial(values.get("serial", ""))
        dealer_code = values.get("dealer_code", "")
        if not serial:
            errors.append(RowError(line, None, dealer_code or None, "Serial is blank"))
            continue
        if not dealer_code:
            errors.append(RowError(line, serial, None, "Dealer code is blank"))
            continue
        rows.append(
            _ParsedRow(
                line=line,
                serial=serial,
                dealer_code=dealer_code,
                dispatch_ref=values.get("dispatch_ref") or None,
            )
        )
    return rows, errors


def _load_dealers(db: Session) -> tuple[dict[str, Dealer], dict[uuid.UUID, str]]:
    """Every dealer, keyed both ways.

    One query for the whole file rather than one per row. Codes are matched
    case-insensitively: a despatch export writes 'd001' where the dealer record
    says 'D001', and failing every row over letter case would make the feature
    useless on day one. The id->code map is for error messages ("already
    allocated to D014"), which name dealers not in this file.
    """
    dealers = db.execute(select(Dealer)).scalars().all()
    return (
        {dealer.code.strip().upper(): dealer for dealer in dealers},
        {dealer.id: dealer.code for dealer in dealers},
    )


def _open_allocations(db: Session, serials: list[str]) -> dict[str, Allocation]:
    found: dict[str, Allocation] = {}
    for chunk in _chunked(serials):
        rows = db.execute(
            select(Allocation).where(
                Allocation.serial.in_(chunk),
                Allocation.status.in_(("allocated", "registered")),
            )
        ).scalars()
        for allocation in rows:
            found[allocation.serial] = allocation
    return found


def _live_warranties(db: Session, serials: list[str]) -> dict[str, Warranty]:
    found: dict[str, Warranty] = {}
    for chunk in _chunked(serials):
        rows = db.execute(
            select(Warranty).where(
                Warranty.serial.in_(chunk), Warranty.status.in_(LIVE_STATUSES)
            )
        ).scalars()
        for warranty in rows:
            found[warranty.serial] = warranty
    return found


def _known_units(db: Session, serials: list[str]) -> set[str]:
    known: set[str] = set()
    for chunk in _chunked(serials):
        known.update(db.execute(select(Unit.token).where(Unit.token.in_(chunk))).scalars())
    return known


def upload_csv(
    db: Session,
    *,
    content: bytes,
    filename: str | None,
    admin_id: uuid.UUID,
    ip: str | None = None,
) -> UploadResult:
    """Parse and apply an allocation CSV. The caller commits, once, at the end.

    One transaction for the whole file on purpose: a half-applied despatch file
    is worse than a rejected one, because nobody can tell which half landed.
    """
    rows, errors = _parse(_decode(content))

    batch = AllocationBatch(filename=filename, uploaded_by_admin_id=admin_id)
    db.add(batch)
    db.flush()
    result = UploadResult(batch=batch, errors=errors)
    # Unparseable lines are still lines the operator sent us, so they count
    # toward the file's row total even though they never became rows.
    result.row_count = len(rows) + len(errors)

    serials = [row.serial for row in rows]
    dealers, dealer_codes = _load_dealers(db)
    open_allocations = _open_allocations(db, serials)
    live_warranties = _live_warranties(db, serials)
    # Manufacturing owns product_units; this upload only ever reads it. A serial
    # with no unit row was never produced, so the row is rejected rather than
    # papered over — which catches a mistyped despatch file on the spot instead
    # of at a counter with a customer waiting.
    known_units = _known_units(db, serials)

    seen: dict[str, uuid.UUID] = {}  # serial -> dealer id claimed earlier in THIS file

    for row in rows:
        if row.serial not in known_units:
            result.errors.append(
                RowError(
                    line=row.line,
                    serial=row.serial,
                    dealer_code=row.dealer_code,
                    reason="No manufactured unit with this code",
                )
            )
            continue

        dealer = dealers.get(row.dealer_code.upper())
        if dealer is None:
            result.errors.append(
                RowError(row.line, row.serial, row.dealer_code, "No dealer with this code")
            )
            continue
        if dealer.status == "closed":
            result.errors.append(
                RowError(row.line, row.serial, row.dealer_code, "This dealer account is closed")
            )
            continue

        # Duplicate inside the same file. Caught here rather than at the unique
        # index, because an IntegrityError would abort the whole upload over one
        # bad pair of lines.
        claimed_by = seen.get(row.serial)
        if claimed_by is not None:
            if claimed_by != dealer.id:
                result.errors.append(
                    RowError(
                        row.line,
                        row.serial,
                        row.dealer_code,
                        "This serial appears twice in this file for different dealers",
                    )
                )
            else:
                result.unchanged_count += 1
            continue

        existing = open_allocations.get(row.serial)
        if existing is not None:
            if existing.dealer_id != dealer.id:
                other = dealer_codes.get(existing.dealer_id, str(existing.dealer_id))
                result.errors.append(
                    RowError(
                        row.line,
                        row.serial,
                        row.dealer_code,
                        f"Already allocated to dealer {other}"
                        + (" and registered" if existing.status == "registered" else ""),
                    )
                )
                continue
            # Same dealer: a safe re-upload. Fill in a dispatch reference if the
            # earlier file did not carry one, and count it as a success.
            if row.dispatch_ref and not existing.dispatch_ref:
                existing.dispatch_ref = row.dispatch_ref
            result.unchanged_count += 1
            seen[row.serial] = dealer.id
            continue

        warranty = live_warranties.get(row.serial)
        if warranty is not None and warranty.dealer_id != dealer.id:
            result.errors.append(
                RowError(
                    row.line,
                    row.serial,
                    row.dealer_code,
                    "This serial already carries a live warranty from another dealer",
                )
            )
            continue

        db.add(
            Allocation(
                serial=row.serial,
                dealer_id=dealer.id,
                batch_id=batch.id,
                # A sold serial keeps its allocation aligned with reality: the
                # unit is out of stock, not available to register again.
                status="registered" if warranty is not None else "allocated",
                dispatch_ref=row.dispatch_ref,
                allocated_at=datetime.now(UTC),
            )
        )
        seen[row.serial] = dealer.id
        result.created_count += 1
    # Sorted by line so the error report reads in the same order as the file the
    # operator is looking at. Parse failures and validation failures are found in
    # different passes and would otherwise interleave arbitrarily.
    result.errors.sort(key=lambda e: e.line)

    batch.row_count = result.row_count
    batch.ok_count = result.ok_count
    batch.error_count = result.error_count
    batch.errors = json.dumps([asdict(e) for e in result.errors[:MAX_STORED_ERRORS]])
    db.flush()

    record_audit(
        db,
        action="upload_allocations",
        entity_type="allocation_batch",
        entity_id=batch.id,
        actor_id=admin_id,
        ip=ip,
        metadata={
            "filename": filename,
            "rows": batch.row_count,
            "created": result.created_count,
            "unchanged": result.unchanged_count,
            "errors": result.error_count,
        },
    )
    logger.info(
        "allocation_upload batch=%s rows=%s created=%s unchanged=%s errors=%s",
        batch.id,
        batch.row_count,
        result.created_count,
        result.unchanged_count,
        result.error_count,
    )
    return result


def parse_errors(batch: AllocationBatch) -> list[RowError]:
    """Read back the stored per-row rejections for a batch detail screen."""
    if not batch.errors:
        return []
    try:
        raw = json.loads(batch.errors)
    except ValueError:  # pragma: no cover - only if the column was hand-edited
        return []
    return [
        RowError(
            line=int(item.get("line", 0)),
            serial=item.get("serial"),
            dealer_code=item.get("dealer_code"),
            reason=str(item.get("reason", "")),
        )
        for item in raw
    ]


def revoke(
    db: Session,
    *,
    allocation: Allocation,
    reason: str,
    admin_id: uuid.UUID,
    ip: str | None = None,
) -> Allocation:
    """Take a serial back off a dealer. Caller commits.

    A REGISTERED allocation cannot be revoked: the sale already happened and the
    customer holds a warranty. Voiding that warranty is the honest way to undo
    it, and it releases the allocation on its own — see warranty.void.
    """
    if not (reason and reason.strip()):
        raise AppError("reason_required", 400, "Revoking an allocation requires a reason")
    if allocation.status == "revoked":
        return allocation
    if allocation.status == "registered":
        raise AppError(
            "allocation_registered",
            409,
            "This unit is already registered. Void the warranty instead — that frees the serial.",
        )

    allocation.status = "revoked"
    allocation.revoked_at = datetime.now(UTC)
    allocation.revoke_reason = reason
    record_audit(
        db,
        action="revoke_allocation",
        entity_type="allocation",
        entity_id=allocation.id,
        actor_id=admin_id,
        reason=reason,
        ip=ip,
        metadata={"serial": allocation.serial, "dealer_id": str(allocation.dealer_id)},
    )
    db.flush()
    return allocation
