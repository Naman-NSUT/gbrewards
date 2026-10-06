"""The catalogue, rendered as PDFs from the data already in the back office.

The app used to draw these four lists itself. Rendering them here means an edit
in the back office is live the moment it is saved, instead of waiting for an app
release, and that nothing is authored twice: every page below is built from the
same rows the admin screens write — products and their points, rewards and their
cost, the published FAQs, and the content doc that holds the terms. There is no
upload step and no second copy to drift out of date.

A4, not the 75x125mm label stock: these are read on a phone and occasionally
printed for a noticeboard, not stuck to a mattress.
"""

import io
from collections.abc import Callable
from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.content_doc import ContentDoc
from app.models.faq import Faq
from app.models.product import Product
from app.models.reward import Reward

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN
BOTTOM = 18 * mm

# Width held back on the right of every catalogue row for its points value, so a
# long product name wraps instead of running underneath the number.
VALUE_COL = 28 * mm

BRAND = (0x0E / 255, 0x2B / 255, 0x52 / 255)  # the navy from the app icon

# The content doc the terms page renders. Same key the admin screen writes, so
# editing "terms" in the back office changes this PDF.
TERMS_KEY = "terms"


@dataclass(frozen=True)
class Doc:
    slug: str
    title: str
    subtitle: str


DOCS: tuple[Doc, ...] = (
    Doc("products", "Products & points", "What each product is worth when you scan it."),
    Doc("rewards", "Redeem options", "What your points can be exchanged for."),
    Doc("faqs", "Questions & answers", "How the programme works."),
    Doc("terms", "Terms & conditions", "The rules of the programme."),
)

DOCS_BY_SLUG = {d.slug: d for d in DOCS}


class _Page:
    """A cursor running down an A4 page that breaks before it runs off.

    A hand-rolled cursor rather than reportlab's platypus: every page here is a
    flat run of short rows, and a frame-and-flowable stack would be more
    machinery than that earns.
    """

    def __init__(self, pdf: canvas.Canvas, doc: Doc) -> None:
        self.pdf = pdf
        self.doc = doc
        self.y = 0.0
        self._start()

    def _start(self) -> None:
        pdf = self.pdf
        pdf.setFillColorRGB(*BRAND)
        pdf.rect(0, PAGE_H - 24 * mm, PAGE_W, 24 * mm, stroke=0, fill=1)
        pdf.setFillColorRGB(1, 1, 1)
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(MARGIN, PAGE_H - 15 * mm, "GOODBED REWARDS")
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(PAGE_W - MARGIN, PAGE_H - 15 * mm, self.doc.title)
        self.y = PAGE_H - 34 * mm

    def space(self, needed: float) -> None:
        """Break the page unless `needed` points are still free below the cursor."""
        if self.y - needed < BOTTOM:
            self.pdf.showPage()
            self._start()

    def heading(self, text: str) -> None:
        lines = simpleSplit(text, "Helvetica-Bold", 12, CONTENT_W)
        self.space(len(lines) * 6 * mm)
        self.pdf.setFillColorRGB(*BRAND)
        self.pdf.setFont("Helvetica-Bold", 12)
        for line in lines:
            self.pdf.drawString(MARGIN, self.y, line)
            self.y -= 5.5 * mm
        self.y -= 1.5 * mm

    def paragraph(self, text: str, *, size: float = 10) -> None:
        for line in simpleSplit(text, "Helvetica", size, CONTENT_W):
            self.space(size * 1.5)
            self.pdf.setFillColorRGB(0.1, 0.1, 0.1)
            self.pdf.setFont("Helvetica", size)
            self.pdf.drawString(MARGIN, self.y, line)
            self.y -= size * 1.5
        self.y -= 2.5 * mm

    def row(self, left: str, right: str, *, note: str | None = None) -> None:
        """A catalogue line: label on the left, its points value hard right."""
        label_w = CONTENT_W - VALUE_COL
        name_lines = simpleSplit(left, "Helvetica-Bold", 11, label_w)

        # Keep the name and its value together; the note may flow over a break.
        self.space(len(name_lines) * 5.5 * mm)
        self.pdf.setFillColorRGB(*BRAND)
        self.pdf.setFont("Helvetica-Bold", 11)
        self.pdf.drawRightString(PAGE_W - MARGIN, self.y, right)
        self.pdf.setFillColorRGB(0, 0, 0)
        for line in name_lines:
            self.pdf.drawString(MARGIN, self.y, line)
            self.y -= 5.5 * mm

        if note:
            for line in simpleSplit(note, "Helvetica", 9, label_w):
                self.space(4.6 * mm)
                self.pdf.setFillColorRGB(0.35, 0.35, 0.35)
                self.pdf.setFont("Helvetica", 9)
                self.pdf.drawString(MARGIN, self.y, line)
                self.y -= 4.6 * mm

        self.y -= 1.5 * mm
        self.space(4 * mm)
        self.pdf.setStrokeColorRGB(0.86, 0.86, 0.86)
        self.pdf.setLineWidth(0.4)
        self.pdf.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.y -= 5 * mm

    def empty(self, text: str) -> None:
        self.pdf.setFillColorRGB(0.45, 0.45, 0.45)
        self.pdf.setFont("Helvetica-Oblique", 10)
        self.pdf.drawString(MARGIN, self.y, text)
        self.y -= 6 * mm


def _products(page: _Page, db: Session) -> None:
    rows = list(
        db.execute(
            select(Product).where(Product.is_active.is_(True)).order_by(Product.name)
        ).scalars()
    )
    page.paragraph(page.doc.subtitle)
    if not rows:
        page.empty("No products have been published yet.")
        return
    for p in rows:
        note = " · ".join(x.strip() for x in (p.size, p.description) if x and x.strip())
        page.row(p.name, f"{p.points_value} pts", note=note or None)


def _rewards(page: _Page, db: Session) -> None:
    rows = list(
        db.execute(
            select(Reward)
            .where(Reward.is_active.is_(True))
            .order_by(Reward.sort_order, Reward.title)
        ).scalars()
    )
    page.paragraph(page.doc.subtitle)
    if not rows:
        page.empty("No rewards have been published yet.")
        return
    for r in rows:
        page.row(r.title, f"{r.points_cost} pts", note=r.description)


def _faqs(page: _Page, db: Session) -> None:
    rows = list(
        db.execute(
            select(Faq).where(Faq.is_published.is_(True)).order_by(Faq.sort_order, Faq.created_at)
        ).scalars()
    )
    if not rows:
        page.empty("No questions have been published yet.")
        return
    for f in rows:
        page.heading(f.question)
        for block in f.answer.split("\n"):
            if block.strip():
                page.paragraph(block.strip())


def _terms(page: _Page, db: Session) -> None:
    doc = db.execute(select(ContentDoc).where(ContentDoc.key == TERMS_KEY)).scalar_one_or_none()
    if doc is None:
        page.empty("The terms have not been published yet.")
        return
    page.heading(doc.title)
    for block in doc.body.split("\n"):
        if block.strip():
            page.paragraph(block.strip())


_RENDERERS: dict[str, Callable[[_Page, Session], None]] = {
    "products": _products,
    "rewards": _rewards,
    "faqs": _faqs,
    "terms": _terms,
}


def render(db: Session, slug: str) -> bytes:
    """One catalogue document, built from the rows the back office holds now."""
    doc = DOCS_BY_SLUG.get(slug)
    if doc is None:
        raise AppError("doc_not_found", 404, "Unknown document")

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.setTitle(f"GoodBed Rewards — {doc.title}")
    _RENDERERS[slug](_Page(pdf, doc), db)
    pdf.showPage()
    pdf.save()
    return buf.getvalue()
