"""Storing a proof of purchase, and reading one back.

Two failures that both end with an approver deciding a five-year warranty on
nothing:

  * A disk that cannot be written escaped `save_upload` as a raw OSError, so the
    customer whose invoice we dropped was shown "Internal server error" instead
    of the friendly retry — and had no reason to think sending it again would
    work.
  * Nothing could READ a stored proof at all. The queue printed the object key
    as text, which is exactly as useful to an approver as printing nothing.

The traversal tests are not theatre. The key reaches `path_for` from a database
column, and a value is not safe merely because it came back from somewhere we
once wrote it.
"""

import io
from datetime import timedelta
from pathlib import Path

import fakeredis
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from app.core.config import settings
from app.core.deps import get_db, get_redis
from app.core.errors import AppError
from app.core.security import create_access_token
from app.dealer.models.warranty import Warranty
from app.dealer.services import registration, self_registration, storage
from app.dealer.services.warranty_dates import business_today
from app.main import create_app
from tests.dealer.factories import (
    make_admin,
    make_dealer,
    make_priced_unit,
    make_staff,
    new_serial,
)

PREFIX = "/api/v1/dealer-admin"
PUB = "/api/v1/public"

PNG = b"\x89PNG\r\n\x1a\n" + b"pretend-invoice-pixels" * 4
JPEG = b"\xff\xd8\xff" + b"a-photo-of-a-bill" * 8

# Every shape of "climb out of the uploads root" we can express in a key. The
# absolute one is the interesting member: see the pathlib test below.
TRAVERSAL_KEYS = [
    "../../../../etc/passwd",
    "proofs/../../../../etc/passwd",
    "/etc/passwd",
    "../" * 12 + "etc/passwd",
]


def _upload(data: bytes, *, content_type: str = "image/png", filename: str = "bill.png"):
    return UploadFile(
        file=io.BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def _client(session_factory, *, raise_server_exceptions: bool = True):
    app = create_app()

    def _get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    # Rate limiters are per IP and every test calls from the same one, so a
    # shared real Redis would make later tests fail on counters earlier tests
    # ran up. A fresh fake per test keeps them independent.
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: fakeredis.FakeRedis(decode_responses=True)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


@pytest.fixture
def client(db, session_factory):  # type: ignore[no-untyped-def]
    with _client(session_factory) as c:
        yield c


@pytest.fixture
def lenient_client(db, session_factory):  # type: ignore[no-untyped-def]
    """A client that RETURNS the 500 instead of re-raising it.

    Starlette's error middleware always re-raises after handing the response to
    the transport, so the only way to assert on what the customer's browser
    actually received is to stop the transport re-raising.
    """
    with _client(session_factory, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def uploads(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Point the store at a scratch directory instead of the deployment's."""
    root = tmp_path / "uploads"
    monkeypatch.setattr(settings, "uploads_dir", str(root))
    return root


@pytest.fixture
def broken_disk(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """An uploads root that is a REGULAR FILE.

    mkdir under a file is ENOTDIR for every user including root, so this test
    means the same thing in CI, on a laptop, and in the container — where the
    Dockerfile leaves the process running as root with /app writable, and a
    permission-based test would simply pass and prove nothing. It stands in for
    the real triggers: ENOSPC on the 5GB disk (~1000 invoices at the 5MB cap),
    a volume that did not remount, a mistyped UPLOADS_DIR.
    """
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file where the uploads disk should be")
    monkeypatch.setattr(settings, "uploads_dir", str(blocker))
    return blocker


def _headers(admin) -> dict[str, str]:  # type: ignore[no-untyped-def]
    token = create_access_token(str(admin.id), "dealer_admin", {"role": admin.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner(db):  # type: ignore[no-untyped-def]
    a = make_admin(db, role="owner")
    db.commit()
    return a


@pytest.fixture
def h(owner):  # type: ignore[no-untyped-def]
    return _headers(owner)


@pytest.fixture
def pending(db, uploads):  # type: ignore[no-untyped-def]
    """A customer self-registration with its invoice really on disk."""
    make_dealer(db, code="D001", name="Sunrise Beds")
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    stored = storage.save_upload(_upload(JPEG, content_type="image/jpeg", filename="bill.jpg"))
    result = self_registration.submit(
        db,
        raw_serial=serial,
        customer_phone="+919812345678",
        customer_name="Meera Iyer",
        purchase_date=business_today() - timedelta(days=3),
        proof_key=stored.key,
        dealer_hint="D001",
    )
    db.commit()
    return result.warranty


# --- Fix 1: a disk that cannot be written ----------------------------------


def test_an_unwritable_disk_is_a_retryable_error_not_a_crash(broken_disk):
    """The mkdir is the first touch of the disk and therefore the first place a
    full or unmounted volume shows up. Escaping raw, it is rendered as
    internal_error and the customer is told nothing they can act on."""
    with pytest.raises(AppError) as excinfo:
        storage.save_upload(_upload(PNG))

    assert excinfo.value.code == "upload_failed"
    assert excinfo.value.status_code == 500
    assert "try again" in excinfo.value.message


def test_the_customer_is_asked_to_retry_rather_than_shown_internal_server_error(
    lenient_client, db, broken_disk
):
    """The whole point of Fix 1, at the layer the customer meets it."""
    make_dealer(db, code="D009", name="Silent Beds")
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    db.commit()

    resp = lenient_client.post(
        f"{PUB}/self-registrations",
        data={
            "serial": serial,
            "customer_name": "Ravi Kumar",
            "customer_phone": "9812300099",
            "purchase_date": business_today().isoformat(),
            "dealer_hint": "D009",
        },
        files={"proof": ("bill.jpg", JPEG, "image/jpeg")},
    )
    assert resp.status_code == 500
    body = resp.json()["error"]
    assert body["code"] == "upload_failed", "internal_error tells the customer nothing"
    assert "try again" in body["message"]

    assert db.query(Warranty).filter_by(serial=serial).one_or_none() is None, (
        "a warranty must not survive an invoice that was never stored"
    )


def test_cleanup_cannot_destroy_the_error_it_is_cleaning_up_after(broken_disk):
    """_remove runs inside an except block that is on its way to raising the
    friendly AppError. unlink() under a regular file raises NotADirectoryError,
    and from there it would replace that error with a bare 500."""
    storage._remove(broken_disk / "proofs" / "2026" / "08" / "deadbeef.png")


# --- Fix 2: reading a proof back -------------------------------------------


def test_a_stored_proof_reads_back_byte_for_byte(uploads):
    stored = storage.save_upload(_upload(PNG))
    loaded = storage.load(stored.key)

    assert loaded.data == PNG
    assert loaded.content_type == "image/png"
    assert loaded.extension == ".png"
    assert loaded.size_bytes == len(PNG)


def test_the_served_type_comes_from_the_bytes_not_from_the_uploader(uploads):
    """A PNG announced as a JPEG. The declared type only buys a friendlier
    error; the magic bytes decide what is stored, and the stored extension
    decides what is served — so a served type is never client-supplied."""
    stored = storage.save_upload(_upload(PNG, content_type="image/jpeg", filename="bill.jpg"))

    assert stored.content_type == "image/png"
    assert storage.load(stored.key).content_type == "image/png"


def test_a_lost_file_is_its_own_error_not_no_proof_attached(uploads):
    """ "The row survived, the file did not" must never read as "the customer
    attached nothing" — that is an approver rejecting a genuine warranty for a
    failure of ours."""
    stored = storage.save_upload(_upload(PNG))
    storage.path_for(stored.key).unlink()

    with pytest.raises(AppError) as excinfo:
        storage.load(stored.key)

    assert excinfo.value.code == "proof_missing"
    assert excinfo.value.status_code == 404


@pytest.mark.parametrize("key", TRAVERSAL_KEYS)
def test_path_for_refuses_a_key_that_climbs_out_of_the_root(uploads, key):
    with pytest.raises(AppError) as excinfo:
        storage.path_for(key)

    assert excinfo.value.code == "invalid_file_key"
    assert excinfo.value.status_code == 400


def test_a_key_we_never_wrote_is_refused_even_inside_the_root(uploads):
    """Staying under the root is not the same as being one of ours.

    save_upload only ever writes the five whitelisted extensions, so a key
    ending in anything else was edited into the column. Serving it would mean
    inventing a content type for bytes we never sniffed — which is how a stored
    .svg or .html comes back as something the browser executes, on the admin
    origin, with an owner logged in.
    """
    planted = uploads / "proofs" / "2026" / "08" / "evil.html"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(b"<script>fetch('/api/v1/dealer-admin/dealers')</script>")

    with pytest.raises(AppError) as excinfo:
        storage.load("proofs/2026/08/evil.html")

    assert excinfo.value.code == "invalid_file_key"
    assert excinfo.value.status_code == 400


def test_an_absolute_key_discards_the_root_instead_of_nesting_under_it(uploads):
    """The trap that makes the guard load-bearing.

    `root / "/etc/passwd"` is NOT `<root>/etc/passwd` — pathlib THROWS THE ROOT
    AWAY and the join evaluates to `/etc/passwd`. Anyone reasoning "we always
    join under the root, so we are safe" is wrong for exactly this key, which is
    why path_for re-checks the result instead of trusting the join.
    """
    root = storage._root()
    assert root / "/etc/passwd" == Path("/etc/passwd")

    with pytest.raises(AppError) as excinfo:
        storage.load("/etc/passwd")
    assert excinfo.value.code == "invalid_file_key"


# --- Fix 2: the endpoint ----------------------------------------------------


def test_the_approver_can_finally_see_the_invoice(client, h, pending):
    resp = client.get(f"{PREFIX}/warranties/{pending.id}/proof", headers=h)

    assert resp.status_code == 200, resp.text
    assert resp.content == JPEG
    assert resp.headers["content-type"].startswith("image/jpeg")
    assert resp.headers["content-disposition"].startswith("inline;")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "private, no-store"


def test_the_invoice_is_not_readable_without_a_token(client, pending):
    assert client.get(f"{PREFIX}/warranties/{pending.id}/proof").status_code == 401


def test_support_may_see_the_evidence_it_may_not_act_on(client, db, pending):
    """Read-level auth on purpose. Support works this queue all day and must be
    able to LOOK; approving is what require_admin_write keeps from them."""
    support = make_admin(db, email="support@example.com", role="support")
    db.commit()
    head = _headers(support)

    assert client.get(f"{PREFIX}/warranties/{pending.id}/proof", headers=head).status_code == 200

    acted = client.post(
        f"{PREFIX}/approvals/{pending.id}/approve",
        headers=head,
        json={"reason": "looks fine"},
    )
    assert acted.status_code == 403


def test_a_warranty_with_no_invoice_says_none_was_attached(client, h, db, uploads):
    """A dealer-registered sale never had a proof, and that is not a fault."""
    dealer = make_dealer(db, code="D050", name="Honest Beds")
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    result = registration.register(
        db,
        staff=staff,
        raw_serial=serial,
        customer_phone="+919812345600",
        customer_name="Asha Kumar",
        invoice_ref="INV-1",
    )
    db.commit()

    resp = client.get(f"{PREFIX}/warranties/{result.warranty.id}/proof", headers=h)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_proof"


def test_a_lost_file_does_not_masquerade_as_a_missing_one_over_http(client, h, db, pending):
    storage.path_for(pending.proof_file_key).unlink()

    resp = client.get(f"{PREFIX}/warranties/{pending.id}/proof", headers=h)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "proof_missing", (
        "an approver who reads this as 'no proof attached' rejects a real warranty"
    )


def test_an_unknown_warranty_is_not_a_missing_proof(client, h, uploads):
    resp = client.get(f"{PREFIX}/warranties/00000000-0000-0000-0000-000000000000/proof", headers=h)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "warranty_not_found"


@pytest.mark.parametrize("key", TRAVERSAL_KEYS)
def test_a_hostile_key_in_the_database_still_cannot_reach_etc_passwd(client, h, db, pending, key):
    """The endpoint is addressed by warranty id, so a caller cannot name a file
    — but the key it uses round-trips through a database column, and that is
    the value path_for is actually defending against."""
    db.query(Warranty).filter_by(id=pending.id).update({"proof_file_key": key})
    db.commit()

    resp = client.get(f"{PREFIX}/warranties/{pending.id}/proof", headers=h)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_file_key"
    assert b"root:" not in resp.content
