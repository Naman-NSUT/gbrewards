"""Dealer QR generation and printable labels.

The dealer programme owns its own serials, so it prints its own labels. A
mattress therefore carries TWO QR codes: the factory's (scanned by a worker
during assembly, `product_units`) and this one (scanned by the dealer at point
of sale, `dealer_units`). They are unrelated tokens and neither can be derived
from the other.

The token is a UUIDv4 and is also printed in text beneath the code, because a
label that has been dragged across a warehouse floor often will not scan and a
shopkeeper needs to be able to type it. Everything a dealer needs to identify the
unit is on the label; nothing sensitive is.
"""

import io
import uuid

import qrcode
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.dealer.models.product import DealerProduct
from app.dealer.models.unit import DealerQrBatch, DealerUnit

# A 60x90mm label — smaller than the factory's 75x125mm stock, since this one
# carries only the dealer code and no marketing copy.
LABEL_W, LABEL_H = 60 * mm, 90 * mm
PAGE_SIZE = (LABEL_W, LABEL_H)
CX = LABEL_W / 2
CONTENT_W = 52 * mm

DEFAULT_TERMS = [
    "Warranty starts when your dealer registers this sale.",
    "Ask for the confirmation SMS before you leave the shop.",
    "Register or check your warranty at the address below.",
]


def generate_batch(
    session: Session,
    *,
    product_id: uuid.UUID,
    quantity: int,
    label: str | None,
    admin_id: uuid.UUID | None,
) -> DealerQrBatch:
    """Create a batch and `quantity` active units. Caller commits."""
    if quantity < 1 or quantity > 10_000:
        raise AppError("invalid_quantity", 400, "Generate between 1 and 10,000 labels at a time")

    product = session.get(DealerProduct, product_id)
    if product is None:
        raise AppError("product_not_found", 404, "Unknown product")

    batch = DealerQrBatch(
        product_id=product_id,
        quantity=quantity,
        label=label,
        created_by_admin_id=admin_id,
    )
    session.add(batch)
    session.flush()

    session.add_all(
        [
            DealerUnit(
                product_id=product_id,
                token=str(uuid.uuid4()),
                status="active",
                batch_id=batch.id,
            )
            for _ in range(quantity)
        ]
    )
    session.flush()
    return batch


def _qr_image(data: str) -> io.BytesIO:
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _draw_label(pdf: canvas.Canvas, product: DealerProduct, unit: DealerUnit) -> None:
    y = LABEL_H - 8 * mm

    pdf.setFillGray(0)
    pdf.setFont("Helvetica-Bold", 11)
    for line in simpleSplit(product.name, "Helvetica-Bold", 11, CONTENT_W)[:2]:
        pdf.drawCentredString(CX, y, line)
        y -= 5 * mm

    pdf.setFont("Helvetica", 7.5)
    pdf.setFillGray(0.35)
    pdf.drawCentredString(CX, y, f"{product.warranty_months}-month warranty")
    y -= 6 * mm

    qr_size = 34 * mm
    pdf.drawImage(
        ImageReader(_qr_image(unit.token)),
        CX - qr_size / 2,
        y - qr_size,
        width=qr_size,
        height=qr_size,
    )
    y -= qr_size + 4 * mm

    # The token in text, so a scuffed label is still usable by hand.
    pdf.setFillGray(0)
    pdf.setFont("Courier-Bold", 6.5)
    pdf.drawCentredString(CX, y, unit.token)
    y -= 6 * mm

    terms = (
        [ln.strip() for ln in product.terms.splitlines() if ln.strip()]
        if product.terms and product.terms.strip()
        else DEFAULT_TERMS
    )
    pdf.setFont("Helvetica", 5.5)
    pdf.setFillGray(0.2)
    for term in terms:
        for line in simpleSplit(term, "Helvetica", 5.5, CONTENT_W):
            if y < 5 * mm:
                return
            pdf.drawCentredString(CX, y, line)
            y -= 2.7 * mm


def render_batch_pdf(session: Session, batch_id: uuid.UUID) -> bytes:
    """One label per unit in the batch, one label per page."""
    batch = session.get(DealerQrBatch, batch_id)
    if batch is None:
        raise AppError("batch_not_found", 404, "Unknown batch")
    product = session.get(DealerProduct, batch.product_id)
    if product is None:
        raise AppError("product_not_found", 404, "Unknown product")

    units = list(
        session.execute(
            select(DealerUnit)
            .where(DealerUnit.batch_id == batch_id)
            .order_by(DealerUnit.created_at, DealerUnit.token)
        ).scalars()
    )

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=PAGE_SIZE)
    for unit in units:
        _draw_label(pdf, product, unit)
        pdf.showPage()
    if not units:
        pdf.showPage()  # a valid one-page PDF beats a corrupt empty file
    pdf.save()
    return buf.getvalue()
