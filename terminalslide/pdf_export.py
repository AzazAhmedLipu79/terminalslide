from __future__ import annotations

import re
import sys
from pathlib import Path

from .parser import Deck, Slide
from .themes import Theme


def _try_import_reportlab():
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor, Color, white, black, lightgrey
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Preformatted
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.pdfgen import canvas as pdfcanvas
        return True
    except ImportError:
        return False


def _hex_to_rgb_float(hex_color: str) -> tuple[float, float, float]:
    """Convert #rrggbb to (r,g,b) in 0-1 range."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r / 255, g / 255, b / 255


def _strip_markdown(text: str) -> str:
    """Remove basic markdown syntax for plain text PDF rendering."""
    # Remove fenced code blocks — handled separately
    text = re.sub(r"```\w*\n.*?```", "", text, flags=re.DOTALL)
    # Bold/italic
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Bullets
    text = re.sub(r"^[-*+]\s+", "• ", text, flags=re.MULTILINE)
    return text.strip()


def _extract_code_blocks(body: str) -> list[tuple[str, str]]:
    """Return list of (lang, code) for all fenced code blocks in body."""
    return re.findall(r"```(\w*)\n(.*?)```", body, re.DOTALL)


def export_pdf(
    deck: Deck,
    theme: Theme,
    output_path: str,
    include_notes: bool = False,
) -> None:
    """
    Export the deck to a PDF file at output_path.
    Raises RuntimeError if reportlab is not installed.
    """
    if not _try_import_reportlab():
        raise RuntimeError(
            "reportlab is not installed. Run: pip install reportlab"
        )

    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Paragraph
    from reportlab.lib.enums import TA_LEFT

    page_width, page_height = LETTER
    margin = 0.75 * inch
    accent_rgb = _hex_to_rgb_float(theme.accent)
    bg_rgb = _hex_to_rgb_float(theme.background)
    fg_rgb = _hex_to_rgb_float(theme.foreground)
    title_rgb = _hex_to_rgb_float(theme.title_color)
    code_bg_rgb = _hex_to_rgb_float(theme.code_background)

    fm = deck.front_matter
    footer_text = " — ".join(filter(None, [fm.author, fm.title, fm.date]))

    c = pdfcanvas.Canvas(output_path, pagesize=LETTER)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SlideTitle",
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=28,
        textColor=HexColor(theme.title_color),
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "SlideBody",
        fontName="Helvetica",
        fontSize=12,
        leading=18,
        textColor=HexColor(theme.foreground),
        spaceAfter=6,
    )
    code_style = ParagraphStyle(
        "SlideCode",
        fontName="Courier",
        fontSize=10,
        leading=14,
        textColor=HexColor(theme.foreground),
        backColor=HexColor(theme.code_background),
        spaceAfter=4,
    )

    total = len(deck.slides)

    for slide_num, slide in enumerate(deck.slides, start=1):
        # Background
        c.setFillColorRGB(*bg_rgb)
        c.rect(0, 0, page_width, page_height, fill=1, stroke=0)

        # Border rectangle
        c.setStrokeColorRGB(*accent_rgb)
        c.setLineWidth(2)
        c.rect(
            margin * 0.5, margin * 0.5,
            page_width - margin, page_height - margin,
            fill=0, stroke=1,
        )

        # Title
        title_y = page_height - margin - 0.2 * inch
        c.setFillColorRGB(*title_rgb)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(margin, title_y, slide.title or "")

        # Divider
        c.setStrokeColorRGB(*accent_rgb)
        c.setLineWidth(0.5)
        c.line(margin, title_y - 8, page_width - margin, title_y - 8)

        # Body content
        y = title_y - 30
        body_without_code = re.sub(r"```\w*\n.*?```", "", slide.body, flags=re.DOTALL)
        code_blocks = _extract_code_blocks(slide.body)

        for line in body_without_code.splitlines():
            if y < margin + 40:
                break
            stripped = line.strip()
            if not stripped:
                y -= 8
                continue

            # Bullet
            if re.match(r"^[-*+]\s+", stripped):
                text = "• " + re.sub(r"^[-*+]\s+", "", stripped)
                text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
                text = re.sub(r"\*(.+?)\*", r"\1", text)
                c.setFillColorRGB(*fg_rgb)
                c.setFont("Helvetica", 12)
                c.drawString(margin + 12, y, text)
                y -= 18
            # Numbered
            elif re.match(r"^\d+\.\s+", stripped):
                text = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
                text = re.sub(r"\*(.+?)\*", r"\1", text)
                c.setFillColorRGB(*fg_rgb)
                c.setFont("Helvetica", 12)
                c.drawString(margin + 12, y, text)
                y -= 18
            else:
                text = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
                text = re.sub(r"\*(.+?)\*", r"\1", text)
                c.setFillColorRGB(*fg_rgb)
                c.setFont("Helvetica", 12)
                c.drawString(margin, y, text)
                y -= 18

        # Code blocks
        for lang, code in code_blocks:
            if y < margin + 40:
                break
            code_lines = code.strip().splitlines()
            block_height = len(code_lines) * 14 + 16
            if y - block_height < margin + 40:
                break
            # Code background rect
            c.setFillColorRGB(*code_bg_rgb)
            c.rect(margin, y - block_height, page_width - 2 * margin, block_height, fill=1, stroke=0)
            c.setFillColorRGB(*fg_rgb)
            c.setFont("Courier", 10)
            code_y = y - 12
            for code_line in code_lines:
                c.drawString(margin + 8, code_y, code_line)
                code_y -= 14
            y -= block_height + 10

        # Notes (if opted in)
        if include_notes and slide.notes:
            c.setFillColorRGB(0.6, 0.6, 0.6)
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(margin, margin + 30, f"Note: {slide.notes[:120]}")

        # Footer: author — title — date
        if footer_text:
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.setFont("Helvetica", 8)
            c.drawString(margin, margin * 0.6, footer_text)

        # Slide number (bottom right)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.setFont("Helvetica", 9)
        c.drawRightString(page_width - margin, margin * 0.6, f"{slide_num} / {total}")

        c.showPage()

    c.save()


def get_output_path(source_path: str) -> str:
    p = Path(source_path)
    return str(p.with_suffix(".pdf"))
