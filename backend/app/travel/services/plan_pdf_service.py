"""Render stored formal travel plan markdown to PDF."""

from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

_FONT_NAME = "TravelPlanCJK"
_BUNDLED_FONT = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoSansSC-Regular.ttf"
)
_FONT_URL = (
    "https://cdn.jsdelivr.net/fontsource/fonts/noto-sans-sc@5.2.5/chinese-simplified-400-normal.ttf"
)

_TEXT_COLOR = (15, 23, 42)
_MUTED_COLOR = (100, 116, 139)
_HEADING_COLOR = (29, 78, 216)

_TABLE_SEP_RE = re.compile(r"^\|\s*[-:| ]+\|\s*$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")


def _register_cjk_fonts(pdf: FPDF, font_path: Path) -> None:
    path = str(font_path)
    for style in ("", "B", "I", "BI"):
        pdf.add_font(_FONT_NAME, style, path)


def _font_candidates() -> list[Path]:
    env_path = os.getenv("TRAVEL_PDF_FONT_PATH")
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(_BUNDLED_FONT)
    candidates.extend(
        [
            Path("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
        ]
    )
    return candidates


def _download_bundled_font() -> Path:
    _BUNDLED_FONT.parent.mkdir(parents=True, exist_ok=True)
    import urllib.request

    urllib.request.urlretrieve(_FONT_URL, _BUNDLED_FONT)
    return _BUNDLED_FONT


def _resolve_font_path() -> Path:
    for candidate in _font_candidates():
        if candidate.is_file() and candidate.stat().st_size > 10_000:
            return candidate

    try:
        return _download_bundled_font()
    except OSError as exc:
        raise RuntimeError(
            "No CJK font found for PDF export. Set TRAVEL_PDF_FONT_PATH or ensure bundled font can be downloaded."
        ) from exc


def sanitize_pdf_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "-", name).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    return (cleaned[:60] or "travel-plan").strip("-") or "travel-plan"


def _normalize_visible_text(text: str) -> str:
    return text.replace("\u200b", "").replace("📍", "地点：").strip()


def _format_inline_text(text: str, *, links_as_text: bool = True) -> str:
    text = _normalize_visible_text(text)
    if links_as_text:
        text = _LINK_RE.sub(r"\1", text)
    else:
        text = _LINK_RE.sub(r"\1 (\2)", text)
    text = _BOLD_RE.sub(r"\1", text)
    text = _ITALIC_RE.sub(r"\1", text)
    return text


def _multi_line(pdf: FPDF, text: str, *, height: float, size: float | None = None) -> None:
    if size is not None:
        pdf.set_font(_FONT_NAME, pdf.font_style, size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        pdf.epw,
        height,
        text,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )


def _set_body_style(pdf: FPDF, *, bold: bool = False, size: float = 11) -> None:
    pdf.set_font(_FONT_NAME, "B" if bold else "", size)
    pdf.set_text_color(*_TEXT_COLOR)


def _write_heading(pdf: FPDF, text: str, *, size: float, color: tuple[int, int, int]) -> None:
    pdf.set_font(_FONT_NAME, "B", size)
    pdf.set_text_color(*color)
    _multi_line(pdf, _format_inline_text(text), height=size * 0.45)
    pdf.ln(1.5)
    _set_body_style(pdf)


def _write_paragraph(pdf: FPDF, text: str, *, size: float = 11, color: tuple[int, int, int] = _TEXT_COLOR) -> None:
    pdf.set_font(_FONT_NAME, "", size)
    pdf.set_text_color(*color)
    _multi_line(pdf, _format_inline_text(text), height=size * 0.45)
    pdf.ln(0.5)


def _write_bullet(pdf: FPDF, text: str, *, indent_level: int = 0) -> None:
    _set_body_style(pdf)
    prefix = f"{'  ' * indent_level}• "
    _multi_line(pdf, prefix + _format_inline_text(text), height=6)


def _write_table_row(pdf: FPDF, row: str, *, header: bool = False) -> None:
    cells = [_format_inline_text(cell) for cell in row.strip().strip("|").split("|")]
    line = "  ".join(cell.strip() for cell in cells if cell.strip())
    if not line:
        return
    pdf.set_font(_FONT_NAME, "B" if header else "", 10)
    pdf.set_text_color(*_TEXT_COLOR)
    _multi_line(pdf, line, height=5.5)
    pdf.ln(0.3)


def _render_markdown_lines(pdf: FPDF, markdown_text: str) -> None:
    lines = markdown_text.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index]
        index += 1
        stripped = raw.strip()
        if not stripped:
            pdf.ln(1.5)
            continue

        if stripped.startswith("# "):
            _write_heading(pdf, stripped[2:], size=18, color=_TEXT_COLOR)
            continue
        if stripped.startswith("## "):
            _write_heading(pdf, stripped[3:], size=14, color=_TEXT_COLOR)
            continue
        if stripped.startswith("### "):
            _write_heading(pdf, stripped[4:], size=12, color=_HEADING_COLOR)
            continue

        if stripped.startswith(">"):
            _write_paragraph(pdf, stripped.lstrip("> ").strip(), size=10, color=_MUTED_COLOR)
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            if _TABLE_SEP_RE.match(stripped):
                continue
            _write_table_row(pdf, stripped, header=True)
            while index < len(lines):
                next_line = lines[index].strip()
                if not next_line.startswith("|"):
                    break
                if _TABLE_SEP_RE.match(next_line):
                    index += 1
                    continue
                _write_table_row(pdf, next_line)
                index += 1
            pdf.ln(1)
            continue

        if stripped.startswith("- "):
            indent_level = 1 if raw.startswith("  ") else 0
            _write_bullet(pdf, stripped[2:], indent_level=indent_level)
            continue

        if stripped.startswith("---"):
            pdf.ln(2)
            continue

        _write_paragraph(pdf, stripped)


def render_markdown_pdf(markdown_text: str, document_title: str) -> bytes:
    del document_title  # title comes from markdown content
    if not markdown_text.strip():
        raise ValueError("Markdown content is empty")

    font_path = _resolve_font_path()

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    _register_cjk_fonts(pdf, font_path)
    _set_body_style(pdf)
    pdf.add_page()
    _render_markdown_lines(pdf, markdown_text)

    buffer = BytesIO()
    pdf.output(buffer)
    pdf_bytes = buffer.getvalue()
    if not pdf_bytes:
        raise RuntimeError("PDF generation produced empty output")
    return pdf_bytes
