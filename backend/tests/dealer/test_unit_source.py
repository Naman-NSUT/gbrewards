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


def test_a_unit_a_worker_already_scanned_is_still_sellable(db):
    """'claimed' means a worker scanned it during assembly, months before it
    reached a shop. Reading it as "already sold" would make every properly
    assembled mattress unregisterable — the single worst way to conflate the
    two systems' vocabularies."""
    from app.models.product_unit import ProductUnit

    serial = new_serial()
    unit = make_unit(db, serial)
    unit.status = "claimed"
    db.commit()

    facts = get_unit_source(db).get(serial)
    assert facts is not None
    assert facts.source_status == "claimed"
    assert db.query(ProductUnit).filter_by(token=serial).one().status == "claimed"


def test_warranty_months_falls_back_when_the_product_has_none(db):
    from app.core.config import settings

    product = make_product(db, name="Unconfigured")
    product.warranty_months = None
    serial = new_serial()
    make_unit(db, serial, product=product)
    db.commit()

    facts = get_unit_source(db).get(serial)
    assert facts is not None
    assert facts.warranty_months == settings.default_warranty_months
