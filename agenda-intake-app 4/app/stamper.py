"""
Stamps a "Received by Clerk's Office" timestamp onto a PDF.

The stamp is placed in the top-right corner of every page, and shows the
date/time the submission was received, in U.S. Eastern time (America/New_York),
which automatically renders as EST or EDT depending on the time of year.
"""
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

EASTERN = ZoneInfo("America/New_York")

STAMP_TEXT_LINE1 = "Received by Town of Sutton Clerk's Office"


def _format_timestamp(dt: datetime) -> str:
    # Example: "07/06/2026 at 2:41 PM EDT"
    return dt.strftime("%m/%d/%Y at %I:%M %p %Z").replace(" 0", " ")


def _make_stamp_overlay(page_width: float, page_height: float, received_dt: datetime, stamp_text: str) -> PdfReader:
    """Builds a one-page PDF containing just the stamp text, sized to match the
    target page so it can be merged on top of every page."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    line1 = stamp_text
    line2 = _format_timestamp(received_dt)

    margin = 18
    box_width = 260
    box_height = 34
    x = page_width - box_width - margin
    y = page_height - box_height - margin

    # Light background box with border so the stamp is legible over any content.
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(0, 0, 0)
    c.roundRect(x, y, box_width, box_height, 4, fill=1, stroke=1)

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 8, y + box_height - 13, line1)
    c.setFont("Helvetica", 8)
    c.drawString(x + 8, y + box_height - 25, line2)

    c.showPage()
    c.save()
    buffer.seek(0)
    return PdfReader(buffer)


def stamp_pdf(
    input_pdf_path: str,
    output_pdf_path: str,
    received_dt: datetime = None,
    stamp_text: str = STAMP_TEXT_LINE1,
) -> datetime:
    """
    Stamps every page of input_pdf_path and writes the result to output_pdf_path.
    Returns the timestamp (Eastern time) that was used, so the caller can
    reference it (e.g., in an email subject line).
    """
    if received_dt is None:
        received_dt = datetime.now(EASTERN)
    else:
        received_dt = received_dt.astimezone(EASTERN)

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        overlay_reader = _make_stamp_overlay(width, height, received_dt, stamp_text)
        page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)

    with open(output_pdf_path, "wb") as f:
        writer.write(f)

    return received_dt
