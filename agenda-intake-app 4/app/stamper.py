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

# Dark red ("firebrick"-family), evocative of a traditional ink "received"
# stamp. Against a white fill this gives a contrast ratio of roughly 10:1,
# well above the 4.5:1 WCAG AA minimum for normal-size text (and above the
# 7:1 AAA threshold), so it stays readable for low-vision users while still
# reading as a clearly distinct, noticeable color rather than plain black.
STAMP_COLOR = (0.545, 0.0, 0.0)  # #8B0000

FONT_BOLD = "Helvetica-Bold"
FONT_REGULAR = "Helvetica"
FONT_SIZE = 8
PADDING_X = 6
PADDING_Y = 5
LINE_GAP = 3


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

    # Size the box to fit the actual text instead of a fixed guess, so it
    # stays compact regardless of how long the stamp text or timestamp is.
    text_width = max(
        c.stringWidth(line1, FONT_BOLD, FONT_SIZE),
        c.stringWidth(line2, FONT_REGULAR, FONT_SIZE),
    )
    box_width = text_width + (PADDING_X * 2)
    box_height = (FONT_SIZE * 2) + LINE_GAP + (PADDING_Y * 2)

    margin = 18
    x = page_width - box_width - margin
    y = page_height - box_height - margin

    # White fill keeps the box legible over any underlying content; the
    # colored border and text are what make it noticeable.
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(*STAMP_COLOR)
    c.setLineWidth(1.25)
    c.roundRect(x, y, box_width, box_height, 4, fill=1, stroke=1)

    line1_baseline = y + box_height - PADDING_Y - FONT_SIZE
    line2_baseline = line1_baseline - LINE_GAP - FONT_SIZE

    c.setFillColorRGB(*STAMP_COLOR)
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawString(x + PADDING_X, line1_baseline, line1)
    c.setFont(FONT_REGULAR, FONT_SIZE)
    c.drawString(x + PADDING_X, line2_baseline, line2)

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
