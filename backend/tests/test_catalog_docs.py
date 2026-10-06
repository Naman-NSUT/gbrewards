"""The four catalogue lists, rendered server-side as PDFs.

The app used to draw these itself from the JSON endpoints. The point of moving
them here is that the back office is the only place the content lives, so what
these pin is the link between a row an admin saved and the bytes a worker opens:
a published product appears, an unpublished one does not, and nothing leaks to a
caller without a token.

Deliberately not a golden-PDF diff. These assert on extracted text, so a layout
or wording change doesn't fail them and teach everyone to re-bless a binary.
"""

import base64
import contextlib
import re
import zlib

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import catalog_pdf
from tests.factories import (
    auth_headers,
    make_content_doc,
    make_faq,
    make_product,
    make_reward,
    make_user,
)


def pdf_text(raw: bytes) -> str:
    """Pull the drawn strings out of a reportlab PDF.

    Its content streams are ASCII85-armoured Flate, so none of the text is
    visible in the raw bytes; undo both filters and collect the (...) literals
    the Tj operators draw. Crude, but it reads what a person would see.
    """
    out: list[str] = []
    for stream in re.findall(rb"stream\r?\n?(.*?)endstream", raw, re.S):
        data = stream.strip()
        if data.endswith(b"~>"):
            data = base64.a85decode(data, adobe=True)
        with contextlib.suppress(zlib.error):
            data = zlib.decompress(data)
        for lit in re.findall(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj", data):
            out.append(lit.replace(rb"\(", b"(").replace(rb"\)", b")").decode("latin-1"))
    return "\n".join(out)


def _get(client: TestClient, user, slug: str):  # type: ignore[no-untyped-def]
    return client.get(f"/api/v1/catalog/docs/{slug}.pdf", headers=auth_headers(user))


def test_the_app_is_offered_all_four_documents(client: TestClient, db: Session) -> None:
    user = make_user(db)
    db.commit()

    resp = client.get("/api/v1/catalog/docs", headers=auth_headers(user))

    assert resp.status_code == 200, resp.text
    assert [d["slug"] for d in resp.json()] == ["products", "rewards", "faqs", "terms"]
    assert all(d["title"] and d["subtitle"] for d in resp.json())


def test_every_offered_document_actually_renders(client: TestClient, db: Session) -> None:
    """The list and the renderers must not drift apart — a listed slug that 404s
    would be a dead link on the Info tab."""
    user = make_user(db)
    db.commit()

    for doc in catalog_pdf.DOCS:
        resp = _get(client, user, doc.slug)
        assert resp.status_code == 200, f"{doc.slug}: {resp.text}"
        assert resp.content.startswith(b"%PDF-"), doc.slug
        assert resp.headers["content-type"] == "application/pdf"


def test_the_products_pdf_is_built_from_the_back_office_rows(
    client: TestClient, db: Session
) -> None:
    make_product(db, name="Ortho Bonnell 8 inch", points_value=45)
    user = make_user(db)
    db.commit()

    text = pdf_text(_get(client, user, "products").content)

    assert "Ortho Bonnell 8 inch" in text
    assert "45 pts" in text


def test_an_unpublished_product_is_not_in_the_pdf(client: TestClient, db: Session) -> None:
    """Deactivating a product in the back office has to take it off the sheet;
    otherwise workers scan for points the programme no longer pays."""
    retired = make_product(db, name="Discontinued Coir 4 inch", points_value=10)
    retired.is_active = False
    make_product(db, name="Latex Plus 6 inch", points_value=60)
    user = make_user(db)
    db.commit()

    text = pdf_text(_get(client, user, "products").content)

    assert "Latex Plus 6 inch" in text
    assert "Discontinued" not in text


def test_the_size_appears_beside_the_product(client: TestClient, db: Session) -> None:
    """Two sizes of one model are different products to the person reading this."""
    product = make_product(db, name="HR Foam 6 inch", points_value=30)
    product.size = "72 x 36 x 6 inch"
    user = make_user(db)
    db.commit()

    assert "72 x 36 x 6 inch" in pdf_text(_get(client, user, "products").content)


def test_the_rewards_pdf_carries_titles_and_costs(client: TestClient, db: Session) -> None:
    make_reward(db, title="Cash 500", points_cost=50)
    user = make_user(db)
    db.commit()

    text = pdf_text(_get(client, user, "rewards").content)

    assert "Cash 500" in text
    assert "50 pts" in text


def test_an_inactive_reward_is_not_offered_on_the_sheet(client: TestClient, db: Session) -> None:
    make_reward(db, title="Withdrawn Hamper", points_cost=90, is_active=False)
    make_reward(db, title="Cash 500", points_cost=50)
    user = make_user(db)
    db.commit()

    text = pdf_text(_get(client, user, "rewards").content)

    assert "Cash 500" in text
    assert "Withdrawn" not in text


def test_the_faq_pdf_carries_both_question_and_answer(client: TestClient, db: Session) -> None:
    make_faq(db, question="When do points land?", answer="As soon as a tag is scanned.")
    user = make_user(db)
    db.commit()

    text = pdf_text(_get(client, user, "faqs").content)

    assert "When do points land?" in text
    assert "As soon as a tag is scanned." in text


def test_an_unpublished_faq_stays_unpublished(client: TestClient, db: Session) -> None:
    make_faq(db, question="Internal draft question", is_published=False)
    user = make_user(db)
    db.commit()

    assert "Internal draft" not in pdf_text(_get(client, user, "faqs").content)


def test_the_terms_pdf_renders_the_content_doc_the_admin_edits(
    client: TestClient, db: Session
) -> None:
    make_content_doc(
        db,
        key=catalog_pdf.TERMS_KEY,
        title="Programme terms",
        body="Points expire after one year.\n\nFraud voids the account.",
    )
    user = make_user(db)
    db.commit()

    text = pdf_text(_get(client, user, "terms").content)

    assert "Programme terms" in text
    assert "Points expire after one year." in text
    assert "Fraud voids the account." in text


def test_an_empty_catalogue_still_renders_a_readable_page(client: TestClient, db: Session) -> None:
    """A fresh install has no products and no terms yet. That must be a sheet
    saying so, not a 500 on the Info tab."""
    user = make_user(db)
    db.commit()

    for slug in ("products", "rewards", "faqs", "terms"):
        resp = _get(client, user, slug)
        assert resp.status_code == 200, f"{slug}: {resp.text}"
        assert "been published yet" in pdf_text(resp.content), slug


def test_an_unknown_slug_is_a_404_not_a_crash(client: TestClient, db: Session) -> None:
    user = make_user(db)
    db.commit()

    resp = _get(client, user, "../../etc/passwd")

    assert resp.status_code == 404


def test_the_catalogue_is_not_readable_without_a_token(client: TestClient) -> None:
    """These name the programme's commercial terms; they are not public."""
    assert client.get("/api/v1/catalog/docs").status_code == 401
    assert client.get("/api/v1/catalog/docs/products.pdf").status_code == 401


def test_a_long_catalogue_spills_onto_further_pages(client: TestClient, db: Session) -> None:
    """One page of A4 holds roughly 25 rows; the real catalogue is bigger, and a
    cursor that never breaks would silently print off the bottom."""
    for i in range(70):
        make_product(db, name=f"Model {i:02d} with a deliberately long name", points_value=i + 1)
    user = make_user(db)
    db.commit()

    raw = _get(client, user, "products").content
    text = pdf_text(raw)

    assert raw.count(b"/Type /Page\n") > 1 or raw.count(b"/Type /Page ") > 1
    # Nothing dropped on the way across the break.
    assert "Model 00 with a deliberately long name" in text
    assert "Model 69 with a deliberately long name" in text
