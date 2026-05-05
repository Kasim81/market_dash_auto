"""
Build `Data_Pipeline_Project_Report.docx`.

Each numbered build step adds a section. Step 2 (current scope) ships
the full equation library — every formula required by the report body
is rendered as a centred display equation in a typography-review probe
section, ready for sign-off.

Subsequent steps embed these equations into the report's body sections.

Usage
-----
    cd manuals
    python build_project_report.py
"""

import os
import sys

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Sibling-module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _omml as M           # noqa: E402
import _equations as EQ     # noqa: E402


OUT_FILENAME = "Data_Pipeline_Project_Report.docx"
REPORT_DATE  = "5 May 2026"


# ── document setup ──────────────────────────────────────────────────────

def setup_document(doc):
    """Apply the report's default page geometry and base typography."""
    for section in doc.sections:
        section.top_margin    = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin   = Inches(1.1)
        section.right_margin  = Inches(1.1)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)


def add_title_page(doc):
    """Centred title block. Page-break appended."""
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("Market Dashboard Auto")
    r.bold = True
    r.font.size = Pt(24)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = subtitle.add_run("Project Report — Data Pipeline & Composite Indicator Layer")
    r.font.size = Pt(14)

    for _ in range(3):
        doc.add_paragraph()

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = meta.add_run(f"Report dated {REPORT_DATE}")
    r.italic = True
    r.font.size = Pt(11)

    doc.add_page_break()


# ── shading helper (re-used for callout boxes / table headers) ──────────

def shade_cell(cell, hex_color):
    """Apply a solid fill colour to a table cell."""
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)


# ── Step 2 probe — equation typography sign-off ─────────────────────────

def add_step2_probe(doc):
    """Render every equation in `_equations.CATALOGUE` for typography review.

    Each catalogue entry is laid out as: bold label, italic one-line
    description (where supplied), centred display equation. Reviewer signs
    off on the typography before Steps 3–5 embed these equations in the
    report's body prose.
    """
    doc.add_heading("Step 2 — Equation library probe", level=1)

    doc.add_paragraph(
        "This section renders every equation slated for inclusion in the "
        "report body, presented as display equations for typography review. "
        "Each equation is preceded by its symbolic label and a one-line "
        "description of where it appears in the report. Reviewer to confirm: "
        "(a) every equation parses as a native Word equation object, "
        "(b) italic-symbol / upright-label conventions are correct, "
        "(c) piecewise / cases constructions render legibly, and "
        "(d) operator spacing is consistent. Once signed off, Steps 3–5 "
        "embed these equations into body prose by reference."
    )

    p = doc.add_paragraph()
    r = p.add_run(f"Equation count: {len(EQ.CATALOGUE)}.")
    r.italic = True

    for label, builder, description in EQ.CATALOGUE:
        # Label paragraph
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after  = Pt(2)
        r = p.add_run(label)
        r.bold = True
        r.font.size = Pt(11)

        # Description paragraph (only when non-empty)
        if description:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            r = p.add_run(description)
            r.italic = True
            r.font.size = Pt(9.5)

        # Centred display equation
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after  = Pt(8)
        M.add_display_equation(p, builder())

    # Closing acceptance statement
    doc.add_paragraph()
    doc.add_paragraph(
        "Acceptance for Step 2: every equation above renders cleanly in Word "
        "and is editable via the equation editor. Any equation requiring "
        "typography adjustment to be flagged before Step 3 begins."
    )


# ── orchestration ───────────────────────────────────────────────────────

def main():
    doc = Document()
    setup_document(doc)
    add_title_page(doc)
    add_step2_probe(doc)

    out_dir  = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, OUT_FILENAME)
    doc.save(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
