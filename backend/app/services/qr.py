"""QR batch generation and printable PDF export (FR-P2, FR-P3).

Tags print onto a *pre-printed* 75x125mm GoodBed label roll: the physical stock
already carries the GOODBED header band, the keyline border and the zone
dividers, so we overprint only the variable "fill" content — product
name/description (Box A), the QR code + token (Box B) and per-product terms &
conditions (Box C). We deliberately do **not** draw any branding/lines or print
the points value on the sticker. One label per PDF page.
"""

import io
import uuid

import qrcode
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.product import Product
from app.models.product_unit import ProductUnit
from app.models.qr_batch import QrBatch
from app.services.audit import record_audit

# --- Label geometry (from the GoodBed 75x125mm dieline) ---------------------
LABEL_W = 75 * mm
LABEL_H = 125 * mm
PAGE_SIZE = (LABEL_W, LABEL_H)
EDGE = 2 * mm  # keyline inset → 71x121mm border
BORDER_W = LABEL_W - 2 * EDGE  # 71mm
BORDER_H = LABEL_H - 2 * EDGE  # 121mm
CONTENT_W = 64 * mm  # printable text width
CONTENT_LEFT = (LABEL_W - CONTENT_W) / 2
CX = LABEL_W / 2

# Zone heights (top → bottom), summing to BORDER_H (121mm).
HEADER_H = 20 * mm
BOX_A_H = 30 * mm  # name + description + points
BOX_B_H = 41 * mm  # QR code
BOX_C_H = 30 * mm  # terms & conditions

# Zone y-boundaries (reportlab origin is bottom-left).
TOP = LABEL_H - EDGE  # 123mm
Y_HEADER = TOP - HEADER_H  # 103mm — header/Box A divider
Y_A = Y_HEADER - BOX_A_H  # 73mm  — Box A/Box B divider
Y_B = Y_A - BOX_B_H  # 32mm  — Box B/Box C divider

# Ink colour for the T&C heading we overprint (Pantone 7694 C match). The GOODBED
# header/tagline itself is pre-printed on the stock, so we no longer draw it.
BRAND_COLOR = HexColor("#2C5D78")

# Fallback terms when a product has no `terms` set.
DEFAULT_TERMS = [
    "This code can be scanned only once.",
    "Multiple or duplicate scans will be treated as an offense.",
    "Valid only on a genuine, unopened product.",
    "Tampered or copied codes are void.",
]


def generate_batch(
    session: Session,
    *,
    product_id: uuid.UUID,
    quantity: int,
    label: str | None,
    admin_id: uuid.UUID,
) -> QrBatch:
    """Create a batch and N active product units. Caller commits."""
    product = session.get(Product, product_id)
    if product is None:
        raise AppError("invalid_code", 404, "Unknown product")

    batch = QrBatch(
        product_id=product_id,
        quantity=quantity,
        created_by_admin_id=admin_id,
        label=label,
    )
    session.add(batch)
    session.flush()

    units = [
        ProductUnit(
            product_id=product_id, token=str(uuid.uuid4()), status="active", batch_id=batch.id
        )
        for _ in range(quantity)
    ]
    session.add_all(units)
    session.flush()

    record_audit(
        session,
        actor_admin_id=admin_id,
        action="generate_batch",
        entity_type="qr_batch",
        entity_id=batch.id,
        metadata={"product_id": str(product_id), "quantity": quantity},
    )
    return batch


def _qr_image(data: str) -> io.BytesIO:
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _draw_lines(
    pdf: canvas.Canvas,
    lines: list[str],
    *,
    x: float,
    y: float,
    leading: float,
    centered: bool = False,
) -> float:
    """Draw pre-wrapped lines top-to-bottom, returning the next y."""
    for line in lines:
        if centered:
            pdf.drawCentredString(x, y, line)
        else:
            pdf.drawString(x, y, line)
        y -= leading
    return y


def _product_terms(product: Product) -> list[str]:
    if product.terms and product.terms.strip():
        return [ln.strip() for ln in product.terms.splitlines() if ln.strip()]
    return DEFAULT_TERMS


def _draw_label(pdf: canvas.Canvas, product: Product, unit: ProductUnit) -> None:
    """Overprint one *pre-printed* 75x125mm GoodBed label with fill content only.

    The stock already carries the GOODBED header, keyline border and zone
    dividers, so we draw nothing decorative here — only the variable content that
    has to land inside the empty boxes. The points value is intentionally omitted
    from the sticker. Zone geometry is retained purely to position the fill.
    """
    # --- Box A: product name + description (no branding, no points) --------
    y = Y_HEADER - 6 * mm
    pdf.setFillGray(0)
    name_lines = simpleSplit(product.name, "Helvetica-Bold", 12, CONTENT_W)[:2]
    pdf.setFont("Helvetica-Bold", 12)
    y = _draw_lines(pdf, name_lines, x=CX, y=y, leading=5 * mm, centered=True)
    if product.description and product.description.strip():
        desc_lines = simpleSplit(product.description.strip(), "Helvetica", 7.5, CONTENT_W)[:3]
        pdf.setFont("Helvetica", 7.5)
        pdf.setFillGray(0.3)
        y = _draw_lines(pdf, desc_lines, x=CX, y=y - 1 * mm, leading=3.6 * mm, centered=True)

    # --- Box B: QR code + human-readable token below it -------------------
    qr_size = 31 * mm
    qr_y = Y_A - 2.5 * mm - qr_size
    pdf.drawImage(
        ImageReader(_qr_image(unit.token)),
        CX - qr_size / 2,
        qr_y,
        width=qr_size,
        height=qr_size,
    )
    # the token printed below the QR so a non-scanning tag is still reconcilable
    pdf.setFillGray(0)
    pdf.setFont("Courier-Bold", 7)
    pdf.drawCentredString(CX, qr_y - 4 * mm, unit.token)

    # --- Box C: terms & conditions ----------------------------------------
    pdf.setFillColor(BRAND_COLOR)
    pdf.setFont("Helvetica-Bold", 6.5)
    pdf.drawString(CONTENT_LEFT, Y_B - 4 * mm, "TERMS & CONDITIONS")
    pdf.setFillGray(0.15)
    pdf.setFont("Helvetica", 6)
    y = Y_B - 7.5 * mm
    for i, term in enumerate(_product_terms(product), start=1):
        lines = simpleSplit(f"{i}. {term}", "Helvetica", 6, CONTENT_W)
        # stop before drawing anything that would spill past the bottom keyline
        if y - len(lines) * 2.9 * mm < EDGE + 1.5 * mm:
            break
        y = _draw_lines(pdf, lines, x=CONTENT_LEFT, y=y, leading=2.9 * mm)

    # reset for next page
    pdf.setFillGray(0)


def render_batch_pdf(session: Session, batch_id: uuid.UUID) -> bytes:
    """One 75x125mm label per unit in the batch."""
    batch = session.get(QrBatch, batch_id)
    if batch is None:
        raise AppError("invalid_code", 404, "Unknown batch")
    product = session.get(Product, batch.product_id)
    assert product is not None

    units = list(
        session.execute(
            select(ProductUnit)
            .where(ProductUnit.batch_id == batch_id)
            .order_by(ProductUnit.created_at)
        ).scalars()
    )

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=PAGE_SIZE)
    for unit in units:
        _draw_label(pdf, product, unit)
        pdf.showPage()
    if not units:
        pdf.showPage()  # keep a valid single-page PDF for an empty batch
    pdf.save()
    return buf.getvalue()


def generate_order(
    session: Session,
    *,
    items: list[tuple[uuid.UUID, int]],
    label: str | None,
    admin_id: uuid.UUID,
) -> list[QrBatch]:
    """Generate one batch per (product, quantity) line — a single QR order.
    Caller commits."""
    batches: list[QrBatch] = []
    for product_id, quantity in items:
        batches.append(
            generate_batch(
                session,
                product_id=product_id,
                quantity=quantity,
                label=label,
                admin_id=admin_id,
            )
        )
    return batches


def render_order_pdf(session: Session, batch_ids: list[uuid.UUID]) -> bytes:
    """Combined label sheet for a QR order — one 75x125mm label per unit across
    all batches, each label carrying its own product's name/terms."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=PAGE_SIZE)
    drew = False
    for batch_id in batch_ids:
        batch = session.get(QrBatch, batch_id)
        if batch is None:
            raise AppError("invalid_code", 404, "Unknown batch")
        product = session.get(Product, batch.product_id)
        assert product is not None
        units = list(
            session.execute(
                select(ProductUnit)
                .where(ProductUnit.batch_id == batch_id)
                .order_by(ProductUnit.created_at)
            ).scalars()
        )
        for unit in units:
            _draw_label(pdf, product, unit)
            pdf.showPage()
            drew = True
    if not drew:
        pdf.showPage()
    pdf.save()
    return buf.getvalue()
