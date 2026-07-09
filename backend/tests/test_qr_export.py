from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.qr import (
    DEFAULT_TERMS,
    _product_terms,
    generate_batch,
    render_batch_pdf,
)
from tests.factories import admin_headers, make_admin


def test_export_returns_pdf(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    h = admin_headers(admin)

    pid = client.post(
        "/api/v1/admin/products", headers=h, json={"name": "Exportable", "points_value": 20}
    ).json()["id"]
    batch_id = client.post(
        f"/api/v1/admin/products/{pid}/batches", headers=h, json={"quantity": 7, "label": "B1"}
    ).json()["id"]

    r = client.get(f"/api/v1/admin/batches/{batch_id}/export?format=pdf", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_render_pdf_multipage(db: Session) -> None:
    admin = make_admin(db)
    db.flush()

    product = Product(name="Bulk", points_value=5)
    db.add(product)
    db.flush()
    batch = generate_batch(db, product_id=product.id, quantity=15, label="bulk", admin_id=admin.id)
    db.flush()

    pdf = render_batch_pdf(db, batch.id)
    assert pdf[:4] == b"%PDF"
    # one 75x125mm label per unit → at least 2 page markers
    assert pdf.count(b"/Type /Page") >= 2 or pdf.count(b"/Page") >= 2


def test_product_terms_parsing() -> None:
    # explicit per-product terms: split into non-empty lines
    p = Product(
        name="X",
        terms="Scan once only.\n\nDuplicate scans are an offense.\n",
        points_value=1,
    )
    assert _product_terms(p) == ["Scan once only.", "Duplicate scans are an offense."]
    # blank / missing terms fall back to the defaults
    assert _product_terms(Product(name="X", points_value=1)) == DEFAULT_TERMS
    assert _product_terms(Product(name="X", terms="   ", points_value=1)) == DEFAULT_TERMS


def test_one_label_page_per_unit(db: Session) -> None:
    admin = make_admin(db)
    db.flush()

    product = Product(
        name="OrthoPillow",
        description="Memory-foam cervical pillow.",
        terms="Scan once only.\nDuplicate scans are an offense.",
        points_value=150,
    )
    db.add(product)
    db.flush()
    batch = generate_batch(db, product_id=product.id, quantity=3, label="b", admin_id=admin.id)
    db.flush()

    pdf = render_batch_pdf(db, batch.id)
    assert pdf[:4] == b"%PDF"
    # one label (page) per unit — subtract the single "/Type /Pages" tree root
    assert pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") == 3


def test_qr_order_multi_product(client: TestClient, db: Session) -> None:
    from sqlalchemy import func, select

    from app.models.product_unit import ProductUnit

    admin = make_admin(db)
    db.commit()
    h = admin_headers(admin)

    p1 = client.post(
        "/api/v1/admin/products", headers=h, json={"name": "SKU-A", "points_value": 10}
    ).json()["id"]
    p2 = client.post(
        "/api/v1/admin/products", headers=h, json={"name": "SKU-B", "points_value": 20}
    ).json()["id"]

    # one order, two product lines with different quantities
    r = client.post(
        "/api/v1/admin/orders",
        headers=h,
        json={
            "label": "Jun order",
            "items": [{"product_id": p1, "quantity": 5}, {"product_id": p2, "quantity": 3}],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["total_units"] == 8
    assert len(body["batches"]) == 2
    names = {b["product_name"]: b["quantity"] for b in body["batches"]}
    assert names == {"SKU-A": 5, "SKU-B": 3}

    # units actually created per product
    assert (
        db.execute(
            select(func.count()).select_from(ProductUnit).where(ProductUnit.product_id == p1)
        ).scalar_one()
        == 5
    )

    # combined PDF export across both batches
    ids = [b["batch_id"] for b in body["batches"]]
    qs = "&".join(f"ids={i}" for i in ids)
    r = client.get(f"/api/v1/admin/orders/export?{qs}&format=pdf", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_qr_order_requires_items(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.post("/api/v1/admin/orders", headers=admin_headers(admin), json={"items": []})
    assert r.status_code == 422
