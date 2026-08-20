"""Unit lookup against the shared database, and serial normalisation.

Before the merge this file tested a mirror, a live read-through and a sync job.
All three are gone: one database means `product_units` IS the source. What is
still worth pinning is that the dealer side reads the real table correctly, and
that a QR payload format change upstream cannot silently break scanning.
"""

import pytest

from app.dealer.services.unitsource import get_unit_source, normalise_serial
from tests.dealer.factories import make_product, make_unit, new_serial


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  ABC-123  ", "abc-123"),
        ("ABC-123", "abc-123"),
        # what GB Rewards actually encodes today: a bare UUIDv4
        ("3F2504E0-4F89-11D3-9A0C-0305E82C3301", "3f2504e0-4f89-11d3-9a0c-0305e82c3301"),
        # the one upstream change that would silently break every scanner
        ("https://gb.example.com/u/abc-123", "abc-123"),
        ("https://gb.example.com/u/abc-123?utm=x", "abc-123"),
        ("https://gb.example.com/u/abc-123/", "abc-123"),
        ("", ""),
    ],
)
def test_normalise_serial_survives_a_payload_format_change(raw, expected):
    assert normalise_serial(raw) == expected


def test_reads_model_and_warranty_terms_from_the_real_product(db):
    product = make_product(db, name="GoodBed HR Foam", months=84)
    serial = new_serial()
    make_unit(db, serial, product=product)
    db.commit()

    facts = get_unit_source(db).get(serial)
    assert facts is not None
    assert facts.model_name == "GoodBed HR Foam"
    assert facts.warranty_months == 84
    assert facts.product_id == product.id
    assert facts.verified is True


def test_unknown_serial_returns_none(db):
    assert get_unit_source(db).get(new_serial()) is None


def test_a_voided_label_cannot_be_registered(db):
    """Labels get voided when a print run is scrapped or a sheet goes missing.
    If a voided label were still registrable, "we lost 200 labels" would become
    200 payable registrations."""
    import pytest as _pytest

    from app.core.errors import AppError
    from app.dealer.services import registration
    from tests.dealer.factories import make_dealer, make_priced_unit, make_staff

    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    unit, _ = make_priced_unit(db, serial, 50)
    unit.status = "void"
    db.commit()

    with _pytest.raises(AppError) as exc:
        registration.register(
            db,
            staff=staff,
            raw_serial=serial,
            customer_phone="+919812345678",
            customer_name="Asha",
            invoice_ref="INV-1",
        )
    assert exc.value.code == "unit_void"


def test_the_dealer_registry_knows_nothing_about_the_factory(db):
    """Full separation: a dealer serial and a factory serial are unrelated, and
    the dealer side cannot see the worker programme's units at all."""
    from app.models.product_unit import ProductUnit

    worker_serial = new_serial()
    dealer_serial = new_serial()
    make_unit(db, dealer_serial)
    db.commit()

    # a factory serial is simply unknown here
    assert get_unit_source(db).get(worker_serial) is None
    assert get_unit_source(db).get(dealer_serial) is not None
    # and nothing the dealer side did created a worker unit
    assert db.query(ProductUnit).count() == 0


def test_warranty_length_comes_from_the_dealer_product(db):
    product = make_product(db, name="Premium", months=84)
    serial = new_serial()
    make_unit(db, serial, product=product)
    db.commit()

    facts = get_unit_source(db).get(serial)
    assert facts is not None
    assert facts.warranty_months == 84
