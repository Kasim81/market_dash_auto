"""
Build `Data_Pipeline_Project_Report.docx`.

Each numbered build step adds a section. Step 1 (this initial scope) lays
down the document skeleton and probes the OMML helper module — output is
a single page containing the title, one inline equation, and one display
equation, sufficient to confirm Word renders them as native, editable
mathematical equations.

Subsequent steps add the full report body content (sections 1–13 and
the appendices).

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

# Sibling-module import for OMML helpers
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _omml as M  # noqa: E402


OUT_FILENAME = "Data_Pipeline_Project_Report.docx"
REPORT_DATE  = "5 May 2026"


# ── document setup ───────────────────────────────────────────────────────

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

    # vertical spacing
    for _ in range(3):
        doc.add_paragraph()

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = meta.add_run(f"Report dated {REPORT_DATE}")
    r.italic = True
    r.font.size = Pt(11)

    doc.add_page_break()


# ── Step 1 probe content ─────────────────────────────────────────────────

def _eq_usd_return():
    """Return the OMML for r_USD = (1+r_local)(1+r_FX) − 1."""
    r_usd   = M.sub(M.run("r"), M.run("USD",   plain=True))
    r_local = M.sub(M.run("r"), M.run("local", plain=True))
    r_fx    = M.sub(M.run("r"), M.run("FX",    plain=True))

    return M.oMath(
        r_usd,
        M.run("="),
        M.paren(M.run("1+") + r_local),
        M.paren(M.run("1+") + r_fx),
        M.run("−1"),
    )


def add_step1_probe(doc):
    """Single section that exercises the OMML pipeline.

    Acceptance: Word opens this document and treats both equations as
    native, editable equation objects.
    """
    doc.add_heading("Step 1 — OMML rendering probe", level=1)

    doc.add_paragraph(
        "This section exists solely to verify that mathematical formulae render "
        "as native Microsoft Word equations (Office Math Markup Language) — "
        "selectable, editable through Word's equation editor, and typeset with "
        "the conventional italic-symbol / upright-label distinction. Once "
        "verified, subsequent build steps populate the report body."
    )

    # Inline equation
    p = doc.add_paragraph()
    p.add_run(
        "The fundamental USD-adjusted return identity used throughout the comp "
        "pipeline is "
    )
    M.add_inline_equation(p, _eq_usd_return())
    p.add_run(", expressed inline within a sentence.")

    # Display equation
    doc.add_paragraph(
        "Presented as a display equation, the same identity reads:"
    )

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    M.add_display_equation(p, _eq_usd_return())

    # Acceptance checklist
    doc.add_paragraph(
        "Acceptance criteria for Step 1, to be confirmed by opening this "
        "document in Microsoft Word:"
    )

    checklist = [
        "The inline equation in the paragraph above is recognised as a single "
        "equation object (a click selects the whole equation, not individual "
        "characters).",
        "The display equation is centred on its own line and independently "
        "editable in Word's equation editor.",
        "Letter symbols (the variable r) are italic; multi-character labels "
        "(USD, local, FX) are upright; numerals and operators render in "
        "standard math typography.",
    ]
    for item in checklist:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(item)

    doc.add_paragraph(
        "Subsequent steps will (Step 2) pre-author the full equation library "
        "for the report, (Steps 3–5) build out the thirteen body sections, "
        "and (Step 6) add the table of contents, page numbers, and final "
        "polish."
    )


# ── orchestration ────────────────────────────────────────────────────────

def main():
    doc = Document()
    setup_document(doc)
    add_title_page(doc)
    add_step1_probe(doc)

    out_dir  = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, OUT_FILENAME)
    doc.save(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
