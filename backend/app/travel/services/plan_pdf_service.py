"""Render stored formal travel plan markdown to PDF."""

from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import Align, TableCellFillMode, XPos, YPos
from fpdf.fonts import FontFace

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
_TABLE_HEADER_FILL = (241, 245, 249)
_BLOCKQUOTE_FILL = (248, 250, 252)
_BLOCKQUOTE_BORDER = (59, 130, 246)

_ALIGN_MAP = {
    "L": Align.L,
    "C": Align.C,
    "R": Align.R,
}

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


def _parse_table_cells(line: str) -> list[str]:
    return [_format_inline_text(cell.strip()) for cell in line.strip().strip("|").split("|")]


def _parse_table_alignments(separator: str) -> list[str]:
    cells = [cell.strip() for cell in separator.strip().strip("|").split("|")]
    alignments: list[str] = []
    for cell in cells:
        if cell.startswith(":") and cell.endswith(":"):
            alignments.append("C")
        elif cell.endswith(":"):
            alignments.append("R")
        else:
            alignments.append("L")
    return alignments


def _table_column_widths(column_count: int, total_width: float) -> tuple[float, ...]:
    if column_count <= 0:
        return (total_width,)
    if column_count == 2:
        ratios = (0.36, 0.64)
    elif column_count == 3:
        ratios = (0.28, 0.22, 0.50)
    elif column_count == 4:
        ratios = (0.22, 0.18, 0.22, 0.38)
    else:
        ratio = 1 / column_count
        ratios = tuple(ratio for _ in range(column_count))
    return tuple(total_width * ratio for ratio in ratios)


def _collect_table_block(lines: list[str], start_index: int) -> tuple[list[str], list[str], list[list[str]], int]:
    header = _parse_table_cells(lines[start_index])
    separator_index = start_index + 1
    if separator_index >= len(lines) or not _TABLE_SEP_RE.match(lines[separator_index].strip()):
        raise ValueError("Invalid markdown table")

    alignments = _parse_table_alignments(lines[separator_index])
    rows: list[list[str]] = []
    index = separator_index + 1
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith("|"):
            break
        if _TABLE_SEP_RE.match(stripped):
            index += 1
            continue
        rows.append(_parse_table_cells(lines[index]))
        index += 1

    return header, alignments, rows, index


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


def _write_blockquote(pdf: FPDF, text: str) -> None:
    content = _format_inline_text(text)
    pdf.set_font(_FONT_NAME, "", 10)
    pdf.set_text_color(*_MUTED_COLOR)
    pdf.set_fill_color(*_BLOCKQUOTE_FILL)
    pdf.set_draw_color(*_BLOCKQUOTE_BORDER)

    x = pdf.l_margin
    y = pdf.get_y()
    pdf.set_x(x + 1.5)
    pdf.multi_cell(
        pdf.epw - 1.5,
        5.5,
        f"  {content}",
        fill=True,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.line(x, y, x, pdf.get_y())
    pdf.ln(1)
    _set_body_style(pdf)


def _write_bullet(pdf: FPDF, text: str, *, indent_level: int = 0) -> None:
    _set_body_style(pdf)
    prefix = f"{'  ' * indent_level}• "
    _multi_line(pdf, prefix + _format_inline_text(text), height=6)


def _write_table(
    pdf: FPDF,
    header: list[str],
    alignments: list[str],
    rows: list[list[str]],
) -> None:
    if not header:
        return

    column_count = len(header)
    normalized_alignments = (alignments + ["L"] * column_count)[:column_count]
    col_widths = _table_column_widths(column_count, pdf.epw)
    headings_style = FontFace(
        family=_FONT_NAME,
        emphasis="BOLD",
        size_pt=10,
        fill_color=_TABLE_HEADER_FILL,
    )

    pdf.set_x(pdf.l_margin)
    pdf.set_font(_FONT_NAME, "", 10)
    pdf.set_text_color(*_TEXT_COLOR)

    with pdf.table(
        width=pdf.epw,
        col_widths=col_widths,
        headings_style=headings_style,
        first_row_as_headings=True,
        line_height=6,
        padding=2.5,
        cell_fill_mode=TableCellFillMode.ROWS,
    ) as table:
        header_row = table.row()
        for index, text in enumerate(header):
            header_row.cell(text, align=_ALIGN_MAP[normalized_alignments[index]])

        for row_data in rows:
            cells = row_data + [""] * max(0, column_count - len(row_data))
            body_row = table.row()
            for index, text in enumerate(cells[:column_count]):
                body_row.cell(text, align=_ALIGN_MAP[normalized_alignments[index]])

    pdf.ln(2)
    _set_body_style(pdf)


def _render_markdown_lines(pdf: FPDF, markdown_text: str) -> None:
    lines = markdown_text.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped:
            pdf.ln(1.5)
            index += 1
            continue

        if stripped.startswith("# "):
            _write_heading(pdf, stripped[2:], size=18, color=_TEXT_COLOR)
            index += 1
            continue
        if stripped.startswith("## "):
            _write_heading(pdf, stripped[3:], size=14, color=_TEXT_COLOR)
            index += 1
            continue
        if stripped.startswith("### "):
            _write_heading(pdf, stripped[4:], size=12, color=_HEADING_COLOR)
            index += 1
            continue

        if stripped.startswith(">"):
            _write_blockquote(pdf, stripped.lstrip("> ").strip())
            index += 1
            continue

        if stripped.startswith("|") and "|" in stripped[1:] and not _TABLE_SEP_RE.match(stripped):
            header, alignments, rows, index = _collect_table_block(lines, index)
            _write_table(pdf, header, alignments, rows)
            continue

        if stripped.startswith("- "):
            indent_level = 1 if raw.startswith("  ") else 0
            _write_bullet(pdf, stripped[2:], indent_level=indent_level)
            index += 1
            continue

        if stripped.startswith("---"):
            pdf.ln(2)
            index += 1
            continue

        _write_paragraph(pdf, stripped)
        index += 1


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
