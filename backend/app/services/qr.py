"""QR batch generation and printable PDF export (FR-P2, FR-P3).

Tags print onto a *pre-printed* 75x125mm GoodBed label roll: the physical stock
already carries the GOODBED header band, the keyline border and the zone
dividers, so we overprint only the variable "fill" content — product
name/description (Box A), the QR code + token (Box B) and per-product terms &
conditions (Box C). We deliberately do **not** draw any branding/lines or print
the points value on the sticker. One label per PDF page.
"""

import io
import secrets
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

# --- QR geometry ------------------------------------------------------------
#
# A QR needs FOUR modules of blank margin on every side or a decoder may not
# find it at all. The old label printed a 29x29 symbol at 31mm inside a 41mm
# box, which left under two modules above it — with one of the stock's own
# pre-printed dividers running along that edge.
#
# A 16-character token is 21x21, so at 27mm each module is 1.29mm (up from
# 1.07mm) AND there is room for the full 5.1mm quiet zone above and below, with
# the printed token clear of it. Both numbers move the right way; printing the
# symbol wider would have made the margin worse, not better.
QR_MODULES = 21  # version 1 — see new_token()
QR_SIZE = 27 * mm
QR_QUIET = 4 * (QR_SIZE / QR_MODULES)  # 4 modules, per the spec

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


# Crockford base32, minus I L O U.
#
# The alphabet is what makes the QR small. A lowercase UUID forces the encoder
# into BYTE mode at 8 bits per character; an uppercase alphanumeric string uses
# ALPHANUMERIC mode at 5.5, so the payload shrinks twice over — fewer characters,
# and fewer bits each. 36-char uuid4 needs a 29x29 version-3 symbol; 16 of these
# fit a 21x21 version 1, which is 38% more ink per module at the same 31mm and
# the whole reason these labels were not scanning off the press.
#
# 16 is exactly the most that still fits version 1 at EC=Q (17 jumps to 25x25),
# so this is the largest token that costs nothing. 32^16 is 2^80 — unguessable
# against a rate-limited scan endpoint.
#
# I, L, O and U are dropped so that nobody reading a scuffed label has to decide
# between 0 and O, or 1 and I and L. The token is printed under the QR precisely
# for the tag that will not scan, so it has to survive being read by a human.
_TOKEN_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
TOKEN_LENGTH = 16


def new_token() -> str:
    """A fresh unit token. Uppercase, unambiguous, and version-1 sized."""
    return "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


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
        ProductUnit(product_id=product_id, token=new_token(), status="active", batch_id=batch.id)
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
    """Render one QR at the highest error correction that still fits version 1.

    EC=Q recovers 25% of a damaged symbol against M's 15%. With a 16-character
    token both are a 21x21 version 1, so the extra robustness is free — and on a
    label that gets handled, scuffed and printed on adhesive stock, free
    robustness is worth taking.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=10,
        # No quiet zone in the image: the label already leaves white around the
        # box, and a border baked into the bitmap would shrink the modules.
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
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
    # Everything on this label is BOLD and solid black.
    #
    # It prints onto adhesive stock and is then read in a warehouse, so the old
    # mix of 6pt regular weight at 15-30% grey was the thing that did not
    # survive the press — grey at that size dithers into something a phone
    # camera and a human both struggle with. Weight and contrast cost nothing
    # here; there is no design reason for any of this type to be light.

    # --- Box A: product name + size + description --------------------------
    y = Y_HEADER - 6 * mm
    pdf.setFillGray(0)
    name_lines = simpleSplit(product.name, "Helvetica-Bold", 12, CONTENT_W)[:2]
    pdf.setFont("Helvetica-Bold", 12)
    y = _draw_lines(pdf, name_lines, x=CX, y=y, leading=5 * mm, centered=True)
    if product.size and product.size.strip():
        # The size is the first thing anyone checks on a mattress tag, so it is
        # set larger than the description and sits directly under the model name.
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawCentredString(CX, y, product.size.strip())
        y -= 4.6 * mm
    if product.description and product.description.strip():
        desc_lines = simpleSplit(product.description.strip(), "Helvetica-Bold", 7.5, CONTENT_W)[:3]
        pdf.setFont("Helvetica-Bold", 7.5)
        y = _draw_lines(pdf, desc_lines, x=CX, y=y - 1 * mm, leading=3.6 * mm, centered=True)

    # --- Box B: QR code + human-readable token below it -------------------
    #
    # QR_SIZE is smaller than the 31mm this used to print at, and that is the
    # point. See the constant: the old label gave the code under two modules of
    # quiet zone where the spec wants four, and a pre-printed divider sits right
    # on that edge. Fewer modules AND a real quiet zone beats a marginally wider
    # symbol crowded by a printed line.
    qr_size = QR_SIZE
    qr_y = Y_A - QR_QUIET - qr_size
    pdf.drawImage(
        ImageReader(_qr_image(unit.token)),
        CX - qr_size / 2,
        qr_y,
        width=qr_size,
        height=qr_size,
    )
    # The token printed below the QR so a tag that will not scan is still
    # reconcilable by hand. It is 16 characters now rather than 36, which buys
    # the room to set it half again as large as before.
    pdf.setFillGray(0)
    pdf.setFont("Courier-Bold", 9)
    # Clear of the quiet zone: text sitting inside it is as bad as a line there.
    pdf.drawCentredString(CX, qr_y - QR_QUIET - 1 * mm, unit.token)

    # --- Box C: terms & conditions ----------------------------------------
    pdf.setFillColor(BRAND_COLOR)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(CONTENT_LEFT, Y_B - 4 * mm, "TERMS & CONDITIONS")
    pdf.setFillGray(0)
    pdf.setFont("Helvetica-Bold", 6.5)
    y = Y_B - 7.5 * mm
    for i, term in enumerate(_product_terms(product), start=1):
        lines = simpleSplit(f"{i}. {term}", "Helvetica-Bold", 6.5, CONTENT_W)
        # stop before drawing anything that would spill past the bottom keyline
        if y - len(lines) * 2.9 * mm < EDGE + 1.5 * mm:
            break
        y = _draw_lines(pdf, lines, x=CONTENT_LEFT, y=y, leading=2.9 * mm)

    # reset for next page
    pdf.setFillGray(0)


def _label_canvas(buf: io.BytesIO) -> canvas.Canvas:
    """A canvas for label output that asks to be printed at ACTUAL SIZE.

    The geometry here matches the official 75x125mm dieline exactly, but the
    back office prints through the browser's print dialog, and that dialog
    scales to whatever page the printer driver defaults to. When the driver's
    default is larger than the label and the dialog is on "Fit to page", the
    75x125 page is enlarged to fill it and only part of it lands on the real
    sticker: text runs into the pre-printed GOODBED header, the terms are
    clipped off both edges, and — worst — a pre-printed divider runs straight
    through the QR's finder patterns, which is enough to stop it scanning.

    /PrintScaling /None is the standard PDF instruction that the document must
    not be scaled. Acrobat honours it and opens its print dialog on "Actual
    size". Browser PDF viewers are inconsistent about it, and this panel prints
    through the browser, so treat it as a default that helps where it is
    respected — NOT as the fix. The fix is the print setup: the driver's paper
    set to a 75x125mm label and the dialog's scale at 100%. Nothing in a PDF can
    override a driver that has been told the page is bigger than it is.
    """
    pdf = canvas.Canvas(buf, pagesize=PAGE_SIZE)
    pdf.setViewerPreference("PrintScaling", "None")
    return pdf


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
    pdf = _label_canvas(buf)
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
    pdf = _label_canvas(buf)
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
