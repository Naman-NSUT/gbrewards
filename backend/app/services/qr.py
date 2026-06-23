"""QR batch generation and printable PDF export (FR-P2, FR-P3)."""

import io
import uuid

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.product import Product
from app.models.product_unit import ProductUnit
from app.models.qr_batch import QrBatch
from app.services.audit import record_audit


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


def render_batch_pdf(session: Session, batch_id: uuid.UUID) -> bytes:
    """A4 grid of QR codes, each labeled with product + batch + short token."""
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
    pdf = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    cols, rows = 3, 4
    margin = 15 * mm
    cell_w = (page_w - 2 * margin) / cols
    cell_h = (page_h - 2 * margin) / rows
    qr_size = min(cell_w, cell_h) - 14 * mm

    for i, unit in enumerate(units):
        slot = i % (cols * rows)
        if i > 0 and slot == 0:
            pdf.showPage()
        col = slot % cols
        row = slot // cols
        x = margin + col * cell_w
        # reportlab origin is bottom-left; lay rows top-to-bottom
        y_top = page_h - margin - row * cell_h

        from reportlab.lib.utils import ImageReader

        qr = ImageReader(_qr_image(unit.token))
        qr_x = x + (cell_w - qr_size) / 2
        qr_y = y_top - qr_size - 4 * mm
        pdf.drawImage(qr, qr_x, qr_y, width=qr_size, height=qr_size)

        pdf.setFont("Helvetica", 7)
        label_lines = [
            product.name,
            batch.label or f"batch {str(batch.id)[:8]}",
            unit.token[:18],
        ]
        text_y = qr_y - 4 * mm
        for line in label_lines:
            pdf.drawCentredString(x + cell_w / 2, text_y, line)
            text_y -= 3.2 * mm

    pdf.showPage()
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
    """Combined printable sheet for a QR order — one section per product/batch,
    each starting on a fresh page with a header."""
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    cols, rows = 3, 4
    margin = 15 * mm
    header_h = 16 * mm
    grid_top = page_h - margin - header_h
    cell_w = (page_w - 2 * margin) / cols
    cell_h = (grid_top - margin) / rows
    qr_size = min(cell_w, cell_h) - 14 * mm
    per_page = cols * rows

    first_section = True
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

        header = f"{product.name} · {len(units)} units · {batch.label or str(batch.id)[:8]}"
        subhead = f"{product.points_value} pts each"

        for i, unit in enumerate(units):
            slot = i % per_page
            if slot == 0:
                if not (first_section and i == 0):
                    pdf.showPage()
                first_section = False
                _order_header(pdf, page_h, margin, header, subhead)
            col = slot % cols
            row = slot // cols
            x = margin + col * cell_w
            y_top = grid_top - row * cell_h
            qr = ImageReader(_qr_image(unit.token))
            qr_x = x + (cell_w - qr_size) / 2
            qr_y = y_top - qr_size - 3 * mm
            pdf.drawImage(qr, qr_x, qr_y, width=qr_size, height=qr_size)
            pdf.setFont("Helvetica", 7)
            pdf.drawCentredString(x + cell_w / 2, qr_y - 4 * mm, unit.token[:18])

        if not units:
            if not first_section:
                pdf.showPage()
            first_section = False
            _order_header(pdf, page_h, margin, header, subhead)

    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def _order_header(
    pdf: canvas.Canvas, page_h: float, margin: float, header: str, subhead: str
) -> None:
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(margin, page_h - margin - 6 * mm, header)
    pdf.setFont("Helvetica", 8)
    pdf.setFillGray(0.45)
    pdf.drawString(margin, page_h - margin - 10 * mm, subhead)
    pdf.setFillGray(0)
