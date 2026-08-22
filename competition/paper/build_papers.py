#!/usr/bin/env python3
# ruff: noqa: E501, RUF001, RUF034
"""Build synchronized Russian and English EraSeMap paper deliverables."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = ROOT / "competition" / "paper"
ASSET_DIR = PAPER_DIR / "assets"
BUILD_DIR = PAPER_DIR / "build"

BLUE = "173B57"
MID_BLUE = "2E6388"
DARK = "17202A"
MUTED = "5D6D7E"
PALE = "EEF4F8"
GRID = "AAB7C4"
WHITE = "FFFFFF"
RED = "A93226"
GREEN = "1E8449"

# narrative_proposal preset + named A4 academic-submission override.
PAGE_WIDTH_DXA = 11907
PAGE_HEIGHT_DXA = 16840
MARGIN_DXA = 1440
TABLE_WIDTH_DXA = PAGE_WIDTH_DXA - 2 * MARGIN_DXA
TABLE_INDENT_DXA = 120


def font_path(bold: bool = False) -> str:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/DejaVuSans-Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("A Unicode TrueType font is required")


def make_system_figure(path: Path, ru: bool) -> None:
    img = Image.new("RGB", (1800, 880), "white")
    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(font_path(True), 48)
    label = ImageFont.truetype(font_path(True), 30)
    small = ImageFont.truetype(font_path(), 25)
    d.text((90, 45), "Логика EraSeMap" if ru else "EraSeMap decision flow", fill="#173B57", font=title)

    boxes = [
        (80, 190, 350, 360, "Запрос\nсубъекта" if ru else "Subject\nrequest"),
        (430, 120, 760, 430, "Типизированный граф\n\nDB · шаблон · индекс\nкэш · backup · model" if ru else "Typed graph\n\nDB · template · index\ncache · backup · model"),
        (850, 120, 1170, 430, "Остаточные пути\n+ обязательные\nканалы evidence" if ru else "Residual paths\n+ mandatory\nevidence channels"),
        (1260, 120, 1690, 430, "COMPLETE\nINCOMPLETE\nUNVERIFIED"),
        (850, 590, 1170, 790, "Минимальный CDC" if ru else "Minimum-cost CDC"),
        (1260, 590, 1690, 790, "Исполнение → replay" if ru else "Execute → replay"),
    ]
    for i, (x1, y1, x2, y2, text) in enumerate(boxes):
        fill = "#EEF4F8" if i < 4 else "#FFF6E6"
        d.rounded_rectangle((x1, y1, x2, y2), radius=24, fill=fill, outline="#2E6388", width=4)
        lines = text.split("\n")
        heights = [d.textbbox((0, 0), line, font=label if j == 0 else small)[3] for j, line in enumerate(lines)]
        total = sum(heights) + 8 * (len(lines) - 1)
        y = (y1 + y2 - total) / 2
        for j, line in enumerate(lines):
            f = label if j == 0 else small
            box = d.textbbox((0, 0), line, font=f)
            d.text(((x1 + x2 - (box[2] - box[0])) / 2, y), line, fill="#17202A", font=f)
            y += heights[j] + 8

    arrows = [((350, 275), (430, 275)), ((760, 275), (850, 275)), ((1170, 275), (1260, 275)), ((1010, 430), (1010, 590)), ((1170, 690), (1260, 690)), ((1480, 590), (1480, 430))]
    for start, end in arrows:
        d.line((start, end), fill="#2E6388", width=8)
        ex, ey = end
        sx, sy = start
        if ex > sx:
            d.polygon([(ex, ey), (ex - 22, ey - 14), (ex - 22, ey + 14)], fill="#2E6388")
        elif ey > sy:
            d.polygon([(ex, ey), (ex - 14, ey - 22), (ex + 14, ey - 22)], fill="#2E6388")
        else:
            d.polygon([(ex, ey), (ex - 14, ey + 22), (ex + 14, ey + 22)], fill="#2E6388")
    img.save(path, dpi=(180, 180))


def make_result_figure(path: Path, ru: bool) -> None:
    img = Image.new("RGB", (1800, 980), "white")
    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(font_path(True), 46)
    label = ImageFont.truetype(font_path(True), 28)
    small = ImageFont.truetype(font_path(), 24)
    d.text((80, 45), "Ключевые измеренные результаты" if ru else "Key measured results", fill="#173B57", font=title)

    d.text((90, 150), "False-complete, mechanism stress (n=75)" if not ru else "Ложный COMPLETE, stress test (n=75)", fill="#17202A", font=label)
    values = [("PCUG", 0, GREEN), ("Typed-node", 75, RED)]
    for idx, (name, value, color) in enumerate(values):
        y = 230 + idx * 120
        d.text((100, y), name, fill="#17202A", font=small)
        d.rectangle((340, y, 1540, y + 55), fill="#ECF0F1")
        width = int(1200 * value / 75)
        if width:
            d.rectangle((340, y, 340 + width, y + 55), fill=f"#{color}")
        d.text((1570, y + 8), f"{value}/75", fill=f"#{color}", font=label)

    d.line((80, 500, 1720, 500), fill="#AAB7C4", width=3)
    d.text((90, 555), "Measured multi-service holdout (20/20 COMPLETE)" if not ru else "Measured multi-service holdout (20/20 COMPLETE)", fill="#17202A", font=label)
    metrics = [
        ("17.64×", "speedup" if not ru else "ускорение"),
        ("94.62%", "fewer written bytes" if not ru else "меньше записанных байтов"),
        ("2.22×10⁻¹⁵", "max ridge weight gap" if not ru else "макс. отклонение ridge weights"),
    ]
    for idx, (value, caption) in enumerate(metrics):
        x1 = 90 + idx * 560
        d.rounded_rectangle((x1, 650, x1 + 500, 890), radius=22, fill="#EEF4F8", outline="#2E6388", width=3)
        box = d.textbbox((0, 0), value, font=title)
        d.text((x1 + (500 - box[2]) / 2, 700), value, fill="#173B57", font=title)
        box2 = d.textbbox((0, 0), caption, font=small)
        d.text((x1 + (500 - box2[2]) / 2, 800), caption, fill="#5D6D7E", font=small)
    img.save(path, dpi=(180, 180))


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_width(cell, width: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width))
    tc_w.set(qn("w:type"), "dxa")


def set_cell_margins(cell, top: int = 80, start: int = 120, bottom: int = 80, end: int = 120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths: list[int]) -> None:
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(TABLE_INDENT_DXA))
    tbl_ind.set(qn("w:type"), "dxa")

    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            set_cell_width(cell, widths[idx])
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_run_font(run, name: str = "Calibri", size: float | None = None, bold: bool | None = None,
                 italic: bool | None = None, color: str | None = None) -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def add_inline(paragraph, text: str, *, default_bold: bool = False, default_italic: bool = False) -> None:
    pattern = re.compile(r"(\*\*.*?\*\*|`.*?`|\*.*?\*)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos:match.start()])
            set_run_font(run, bold=default_bold, italic=default_italic)
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, bold=True, italic=default_italic)
        elif token.startswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, name="Menlo", size=9.5, color=BLUE)
        else:
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, bold=default_bold, italic=True)
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        set_run_font(run, bold=default_bold, italic=default_italic)


def add_page_field(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_char1, instr, fld_char2])
    set_run_font(run, size=9, color=MUTED)


def configure_document(doc: Document, ru: bool) -> None:
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Inches(1.0)
    sec.bottom_margin = Inches(1.0)
    sec.left_margin = Inches(1.0)
    sec.right_margin = Inches(1.0)
    sec.header_distance = Inches(0.492)
    sec.footer_distance = Inches(0.492)
    sec.different_first_page_header_footer = True

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor.from_string(DARK)
    pf = normal.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.space_before = Pt(0)
    pf.space_after = Pt(8)
    pf.line_spacing = 1.333

    heading_tokens = {
        "Heading 1": (16, BLUE, 18, 10),
        "Heading 2": (13, MID_BLUE, 12, 6),
        "Heading 3": (12, BLUE, 8, 4),
    }
    for name, (size, color, before, after) in heading_tokens.items():
        style = doc.styles[name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    for style_name in ("List Bullet", "List Number"):
        style = doc.styles[style_name]
        style.font.name = "Calibri"
        style.font.size = Pt(11)
        style.paragraph_format.left_indent = Inches(0.375)
        style.paragraph_format.first_line_indent = Inches(-0.194)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.line_spacing = 1.208

    for name in ("Formula", "Figure Caption", "Callout", "Code Block", "Numbered Item"):
        if name not in [style.name for style in doc.styles]:
            doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    formula = doc.styles["Formula"]
    formula.font.name = "Cambria Math"
    formula.font.size = Pt(11.5)
    formula.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    formula.paragraph_format.space_before = Pt(4)
    formula.paragraph_format.space_after = Pt(8)
    formula.paragraph_format.keep_together = True
    caption = doc.styles["Figure Caption"]
    caption.font.name = "Calibri"
    caption.font.size = Pt(9.5)
    caption.font.italic = True
    caption.font.color.rgb = RGBColor.from_string(MUTED)
    caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_before = Pt(4)
    caption.paragraph_format.space_after = Pt(10)
    callout = doc.styles["Callout"]
    callout.font.name = "Calibri"
    callout.font.size = Pt(11)
    callout.font.italic = True
    callout.font.color.rgb = RGBColor.from_string(BLUE)
    callout.paragraph_format.left_indent = Inches(0.25)
    callout.paragraph_format.right_indent = Inches(0.25)
    callout.paragraph_format.space_before = Pt(6)
    callout.paragraph_format.space_after = Pt(10)
    code = doc.styles["Code Block"]
    code.font.name = "Menlo"
    code.font.size = Pt(8.5)
    code.paragraph_format.left_indent = Inches(0.25)
    code.paragraph_format.space_after = Pt(2)
    code.paragraph_format.line_spacing = 1.0
    numbered = doc.styles["Numbered Item"]
    numbered.font.name = "Calibri"
    numbered.font.size = Pt(11)
    numbered.paragraph_format.left_indent = Inches(0.375)
    numbered.paragraph_format.first_line_indent = Inches(-0.194)
    numbered.paragraph_format.space_after = Pt(4)
    numbered.paragraph_format.line_spacing = 1.208

    header = sec.header.paragraphs[0]
    header.text = "EraSeMap | " + ("Научная работа" if ru else "Research paper")
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_run_font(header.runs[0], size=9, bold=True, color=MUTED)
    footer = sec.footer.paragraphs[0]
    add_page_field(footer)


def add_cover(doc: Document, title: str, ru: bool) -> None:
    for _ in range(5):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
    kicker = doc.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = kicker.add_run("НАУЧНО-ИССЛЕДОВАТЕЛЬСКАЯ РАБОТА" if ru else "SCIENTIFIC RESEARCH PAPER")
    set_run_font(run, size=11, bold=True, color=MID_BLUE)
    kicker.paragraph_format.space_after = Pt(18)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(14)
    r = p.add_run(title)
    set_run_font(r, size=27, bold=True, color=BLUE)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.paragraph_format.space_after = Pt(52)
    r = sub.add_run("Proof-carrying biometric erasure audit" if not ru else "Доказательный аудит удаления биометрических данных")
    set_run_font(r, size=14, italic=True, color=MUTED)

    fields = [
        ("Автор" if ru else "Author", "____________________________"),
        ("Организация" if ru else "Affiliation", "____________________________"),
        ("Научный руководитель" if ru else "Supervisor", "____________________________"),
    ]
    table = doc.add_table(rows=len(fields), cols=2)
    widths = [2450, TABLE_WIDTH_DXA - 2450]
    set_table_geometry(table, widths)
    for i, (key, value) in enumerate(fields):
        table.cell(i, 0).text = key
        table.cell(i, 1).text = value
        for j, cell in enumerate(table.rows[i].cells):
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(4)
                for run in paragraph.runs:
                    set_run_font(run, size=11, bold=(j == 0), color=MUTED if j == 0 else DARK)
            set_cell_shading(cell, WHITE)
    # Remove table borders on the cover.
    tbl_borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        tbl_borders.append(el)
    table._tbl.tblPr.append(tbl_borders)
    # The metadata grid is a layout table; mark its first row so assistive
    # technology does not report an unlabeled table structure.
    set_repeat_table_header(table.rows[0])

    # Keep the cover on one A4 page even when a Russian metadata label wraps.
    for _ in range(2):
        doc.add_paragraph()
    year = doc.add_paragraph()
    year.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = year.add_run("2026")
    set_run_font(r, size=11, bold=True, color=MUTED)
    doc.add_page_break()


def parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    i = start
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
        if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            rows.append(cells)
        i += 1
    return rows, i


def table_widths(cols: int) -> list[int]:
    if cols == 2:
        return [3000, TABLE_WIDTH_DXA - 3000]
    if cols == 3:
        return [2300, 2450, TABLE_WIDTH_DXA - 4750]
    if cols == 4:
        return [1900, 1750, 1750, TABLE_WIDTH_DXA - 5400]
    base = TABLE_WIDTH_DXA // cols
    return [base] * (cols - 1) + [TABLE_WIDTH_DXA - base * (cols - 1)]


def add_table(doc: Document, rows: list[list[str]]) -> None:
    if not rows:
        return
    cols = len(rows[0])
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    set_table_geometry(table, table_widths(cols))
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            cell = table.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.08
            add_inline(p, text, default_bold=(i == 0))
            for run in p.runs:
                set_run_font(run, size=9.2, bold=(i == 0 or run.bold))
            if i == 0:
                set_cell_shading(cell, PALE)
    set_repeat_table_header(table.rows[0])
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def add_figure(doc: Document, path: Path, caption: str, alt_text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_together = True
    shape = p.add_run().add_picture(str(path), width=Inches(6.1))
    shape._inline.docPr.set("descr", alt_text)
    shape._inline.docPr.set("title", caption.split(".", 1)[0])
    cap = doc.add_paragraph(caption, style="Figure Caption")
    cap.paragraph_format.keep_with_next = False


def build_from_markdown(source: Path, output: Path, ru: bool) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    title = lines[0][2:].strip()
    doc = Document()
    configure_document(doc, ru)
    add_cover(doc, title, ru)

    system_fig = ASSET_DIR / ("system-flow-ru.png" if ru else "system-flow-en.png")
    result_fig = ASSET_DIR / ("results-ru.png" if ru else "results-en.png")
    inserted_system = False
    inserted_results = False
    in_code = False
    skip_metadata = True
    i = 1
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if skip_metadata:
            if line.startswith("## "):
                skip_metadata = False
            else:
                i += 1
                continue
        if line.startswith("```"):
            in_code = not in_code
            i += 1
            continue
        if in_code:
            p = doc.add_paragraph(style="Code Block")
            p.add_run(raw)
            i += 1
            continue
        if not line:
            i += 1
            continue
        if line.startswith("|"):
            rows, i = parse_table(lines, i)
            add_table(doc, rows)
            continue
        if line.startswith("## "):
            heading = line[3:]
            doc.add_paragraph(heading, style="Heading 1")
            if (heading in ("2. Related Work and Novelty Boundary", "2. Предшествующие работы и граница новизны")) and not inserted_system:
                add_figure(
                    doc,
                    system_fig,
                    ("Рисунок 1. От запроса субъекта к проверенному завершению через остаточные пути, CDC и повторный аудит. Составлено автором по протоколу EraSeMap." if ru else "Figure 1. From a subject request to verified completion through residual paths, CDC, and replay. Author-generated from the EraSeMap protocol."),
                    ("Схема: запрос удаления проходит через граф остаточных путей, проверяющие каналы, выбор CDC, исполнение действий и повторный аудит до COMPLETE." if ru else "Flow diagram: an erasure request passes through the residual-path graph, verifier channels, CDC selection, action execution, and replayed audit before COMPLETE."),
                )
                inserted_system = True
            if (heading in ("9. Discussion", "9. Обсуждение")) and not inserted_results:
                add_figure(
                    doc,
                    result_fig,
                    ("Рисунок 2. Результат стресс-теста механизма и эффективность измеренного многосервисного испытания. Составлено автором по зафиксированным результатам." if ru else "Figure 2. Mechanism-stress result and measured multi-service holdout efficiency. Author-generated from the frozen results."),
                    ("Диаграмма: PCUG даёт 0 из 75 ложных COMPLETE против 75 из 75 у typed-node; многосервисный CDC достигает 17,64-кратного ускорения и сокращает записанные байты на 94,62 процента." if ru else "Results chart: PCUG has 0 of 75 false COMPLETE verdicts versus 75 of 75 for typed-node; multi-service CDC reaches 17.64-fold speedup and 94.62 percent fewer written bytes."),
                )
                inserted_results = True
            i += 1
            continue
        if line.startswith("### "):
            doc.add_paragraph(line[4:], style="Heading 2")
            i += 1
            continue
        if line.startswith("#### "):
            doc.add_paragraph(line[5:], style="Heading 3")
            i += 1
            continue
        if line.startswith("> "):
            p = doc.add_paragraph(style="Callout")
            add_inline(p, line[2:])
            i += 1
            continue
        numbered_match = re.match(r"^(\d+)\. (.*)", line)
        if numbered_match:
            p = doc.add_paragraph(style="Numbered Item")
            prefix = p.add_run(f"{numbered_match.group(1)}. ")
            set_run_font(prefix)
            add_inline(p, numbered_match.group(2))
            i += 1
            continue
        if line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            add_inline(p, line[2:])
            i += 1
            continue
        if line.startswith("**") and line.endswith("**") and len(line) > 4:
            p = doc.add_paragraph(style="Formula")
            text = line[2:-2]
            run = p.add_run(text)
            set_run_font(run, name="Cambria Math", size=11.5)
            i += 1
            continue
        p = doc.add_paragraph()
        p.paragraph_format.widow_control = True
        add_inline(p, line)
        i += 1

    core = doc.core_properties
    core.title = title
    core.subject = "Biometric erasure auditing, PCUG, CDC, and machine unlearning"
    core.author = "EraSeMap project — author fields intentionally left for submission"
    core.keywords = "biometric erasure, machine unlearning, data lineage, verifiable deletion"
    core.comments = "Design preset: narrative_proposal; named override: A4 academic submission geometry."
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    make_system_figure(ASSET_DIR / "system-flow-en.png", False)
    make_system_figure(ASSET_DIR / "system-flow-ru.png", True)
    make_result_figure(ASSET_DIR / "results-en.png", False)
    make_result_figure(ASSET_DIR / "results-ru.png", True)
    jobs = [
        (PAPER_DIR / "EraSeMap_scientific_paper_EN.md", PAPER_DIR / "EraSeMap_scientific_paper_EN.docx", False),
        (PAPER_DIR / "EraSeMap_scientific_paper_RU.md", PAPER_DIR / "EraSeMap_scientific_paper_RU.docx", True),
    ]
    for source, output, ru in jobs:
        build_from_markdown(source, output, ru)
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
