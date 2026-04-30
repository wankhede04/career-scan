"""
Render resume/base_resume.md to resume/base_resume.pdf.

Lightweight pure-Python renderer using reportlab + markdown2; produces a
single-column letter-sized PDF with sensible typography for resumes.

Usage:
    python -m applier.render_resume_pdf [--input resume/base_resume.md] [--output resume/base_resume.pdf]
"""
from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import markdown2
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"],
            fontSize=20, leading=24, spaceAfter=6, textColor=colors.HexColor("#1F4E79"),
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontSize=12, leading=15, spaceBefore=10, spaceAfter=4,
            textColor=colors.HexColor("#1F4E79"), textTransform="uppercase",
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"],
            fontSize=10.5, leading=13, spaceBefore=6, spaceAfter=2,
            textColor=colors.HexColor("#222222"), fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"],
            fontSize=10, leading=13, spaceAfter=4, textColor=colors.HexColor("#222222"),
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["BodyText"],
            fontSize=9.5, leading=12, textColor=colors.HexColor("#555555"),
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["BodyText"],
            fontSize=10, leading=13, leftIndent=12, bulletIndent=0,
            textColor=colors.HexColor("#222222"), spaceAfter=2,
        ),
    }


_INLINE_HTML_OK = re.compile(r"</?(b|i|strong|em|u|br|a|font|sub|sup)(\s[^>]*)?/?>", re.IGNORECASE)


def _inline(html_fragment: str) -> str:
    """markdown2 returns HTML; reportlab Paragraph supports a small subset.
    Translate <strong>/<em> to <b>/<i> and strip anything else risky.
    """
    out = re.sub(r"<strong>", "<b>", html_fragment, flags=re.IGNORECASE)
    out = re.sub(r"</strong>", "</b>", out, flags=re.IGNORECASE)
    out = re.sub(r"<em>", "<i>", out, flags=re.IGNORECASE)
    out = re.sub(r"</em>", "</i>", out, flags=re.IGNORECASE)
    # drop any remaining tags Paragraph doesn't grok
    out = re.sub(r"<(?!/?(b|i|u|br|font|a|sub|sup)\b)[^>]+>", "", out, flags=re.IGNORECASE)
    return out.strip()


def _flowables_from_markdown(md_text: str, styles) -> list:
    """Parse the markdown into reportlab flowables.

    Hand-rolled walker over the html5 tree from markdown2 — keeps the renderer
    dependency-light and avoids weasyprint's native libs.
    """
    html = markdown2.markdown(md_text, extras=["tables", "fenced-code-blocks"])
    # Wrap to ensure single root for ET
    root = ET.fromstring(f"<root>{html}</root>")

    flow: list = []

    def _text_of(el) -> str:
        return "".join(ET.tostring(c, encoding="unicode") if c.tag != "p" else (c.text or "") for c in el)

    def _inner_html(el) -> str:
        # Serialize child nodes back to HTML so inline tags survive.
        chunks: list[str] = []
        if el.text:
            chunks.append(el.text)
        for c in list(el):
            chunks.append(ET.tostring(c, encoding="unicode"))
        return _inline("".join(chunks))

    for child in list(root):
        tag = child.tag.lower()
        if tag == "h1":
            flow.append(Paragraph(_inner_html(child), styles["h1"]))
        elif tag == "h2":
            flow.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#1F4E79"), spaceBefore=8, spaceAfter=2))
            flow.append(Paragraph(_inner_html(child).upper(), styles["h2"]))
        elif tag == "h3":
            flow.append(Paragraph(_inner_html(child), styles["h3"]))
        elif tag == "p":
            flow.append(Paragraph(_inner_html(child), styles["body"]))
        elif tag in ("ul", "ol"):
            items = []
            for li in child.findall("li"):
                items.append(ListItem(Paragraph(_inner_html(li), styles["bullet"]), leftIndent=10))
            flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14, bulletFontSize=8))
            flow.append(Spacer(1, 4))
        elif tag == "hr":
            flow.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#bbbbbb"), spaceBefore=4, spaceAfter=4))
        else:
            inner = _inner_html(child)
            if inner:
                flow.append(Paragraph(inner, styles["body"]))
    return flow


def render_md_to_pdf(md_path: Path, pdf_path: Path) -> Path:
    md_text = md_path.read_text()
    styles = _styles()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=md_path.stem.replace("_", " ").title(),
    )
    flow = _flowables_from_markdown(md_text, styles)
    doc.build(flow)
    logger.info("wrote %s (%d bytes)", pdf_path, pdf_path.stat().st_size)
    return pdf_path


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Render resume markdown to PDF")
    parser.add_argument("--input", type=Path, default=Path("resume/base_resume.md"))
    parser.add_argument("--output", type=Path, default=Path("resume/base_resume.pdf"))
    args = parser.parse_args(argv)
    render_md_to_pdf(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
