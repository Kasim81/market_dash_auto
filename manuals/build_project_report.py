"""
Build `Data_Pipeline_Project_Report.docx`.

Each numbered build step adds content. Step 3 (current scope) authors
Sections 1–5 of the report body: Executive Summary, Problem Statement,
System Overview, Data Architecture & Source Catalogue, and Pipeline
Design Principles. The Step 2 equation-library probe remains appended
at the document's tail for reviewer typography sign-off; it is removed
in Step 6.

Subsequent steps add Sections 6–13, the appendices, and final polish.

Usage
-----
    cd manuals
    python build_project_report.py
"""

import os
import sys

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Sibling-module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _omml as M           # noqa: E402
import _equations as EQ     # noqa: E402


OUT_FILENAME = "Data_Pipeline_Project_Report.docx"
REPORT_DATE  = "5 May 2026"


# Colour palette (consistent across the document)
COLOR_HEADER     = "D9E2F3"   # slate-blue header rows
COLOR_CALLOUT    = "F2F2F2"   # light-grey callout fill
COLOR_GREEN      = "DEEBD8"   # status: live / fresh
COLOR_AMBER      = "FFF2CC"   # status: partial / stale
COLOR_PINK       = "FBDDDD"   # status: missing / gap
COLOR_DIAGRAM    = "EAF1FB"   # data-flow box fill


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


# ── styling helpers ─────────────────────────────────────────────────────

def shade_cell(cell, hex_color):
    """Apply a solid fill colour to a table cell."""
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)


def remove_cell_borders(cell):
    """Strip all borders from a table cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "nil")
        tcBorders.append(b)
    tcPr.append(tcBorders)


def add_section_heading(doc, number, title):
    """Top-level numbered section. Starts on a fresh page."""
    doc.add_page_break()
    h = doc.add_heading(f"{number}.  {title}", level=1)
    h.paragraph_format.space_before = Pt(0)
    h.paragraph_format.space_after  = Pt(8)


def add_subsection_heading(doc, number, title):
    """Sub-numbered heading."""
    h = doc.add_heading(f"{number}  {title}", level=2)
    h.paragraph_format.space_before = Pt(10)
    h.paragraph_format.space_after  = Pt(2)


def add_paragraph(doc, text, *, italic=False, bold=False, size=10.5,
                  align=None, space_after=6):
    """Body paragraph with consistent formatting."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    r.italic = italic
    r.bold   = bold
    r.font.size = Pt(size)
    return p


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run(text)
    r.font.size = Pt(10.5)
    return p


def add_callout(doc, heading, body, fill=COLOR_CALLOUT):
    """Single-cell shaded box used for asides / architectural notes."""
    t = doc.add_table(rows=1, cols=1)
    cell = t.cell(0, 0)
    shade_cell(cell, fill)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    # Heading paragraph inside cell
    p1 = cell.paragraphs[0]
    p1.paragraph_format.space_after = Pt(2)
    r = p1.add_run(heading)
    r.bold = True
    r.font.size = Pt(10)
    # Body paragraph
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    r = p2.add_run(body)
    r.font.size = Pt(10)
    doc.add_paragraph()  # vertical breathing room


def add_shaded_table(doc, headers, rows, *, header_fill=COLOR_HEADER,
                     row_fills=None, col_widths=None):
    """Standard table: shaded header row, optional per-row fills.

    `rows`     — list of tuples (each tuple == one body row).
    `row_fills`— optional list[str|None] same length as rows.
    `col_widths` — optional list[Inches] same length as headers.
    """
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"

    # Header
    for ci, h in enumerate(headers):
        c = t.cell(0, ci)
        c.text = ""
        shade_cell(c, header_fill)
        p = c.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after  = Pt(2)
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(9.5)

    # Body
    for ri, row in enumerate(rows, start=1):
        fill = row_fills[ri - 1] if row_fills else None
        for ci, v in enumerate(row):
            c = t.cell(ri, ci)
            c.text = ""
            if fill:
                shade_cell(c, fill)
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after  = Pt(1)
            r = p.add_run(str(v))
            r.font.size = Pt(9.5)

    if col_widths:
        for ci, w in enumerate(col_widths):
            for ri in range(1 + len(rows)):
                t.cell(ri, ci).width = w

    doc.add_paragraph()  # spacing after table


def add_dataflow_diagram(doc, steps):
    """Vertical box-and-arrow diagram, rendered as a 1-column borderless
    table. `steps` is a list[str]; ' → ' arrows are inserted between rows.

    The diagram is purely text + cell-shading — no images, no SVG —
    deliberately, so the document renders identically on every Word build.
    """
    nrows = 2 * len(steps) - 1
    t = doc.add_table(rows=nrows, cols=1)
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for idx, step in enumerate(steps):
        # Box row
        cell = t.cell(2 * idx, 0)
        cell.text = ""
        shade_cell(cell, COLOR_DIAGRAM)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after  = Pt(3)
        r = p.add_run(step)
        r.font.size = Pt(9.5)
        r.bold = True

        # Arrow row (between boxes only)
        if idx < len(steps) - 1:
            arrow_cell = t.cell(2 * idx + 1, 0)
            arrow_cell.text = ""
            remove_cell_borders(arrow_cell)
            p = arrow_cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after  = Pt(0)
            r = p.add_run("▼")
            r.font.size = Pt(10)

    doc.add_paragraph()


def add_eq_inline(paragraph, builder):
    M.add_inline_equation(paragraph, builder())


def add_eq_display(doc, builder, *, eq_number=None):
    """Centred display equation with optional right-aligned (n.n) label."""
    if eq_number is None:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after  = Pt(8)
        M.add_display_equation(p, builder())
        return

    # Two-cell borderless table: equation centred, number right-aligned.
    t = doc.add_table(rows=1, cols=2)
    t.autofit = False
    t.columns[0].width = Inches(5.4)
    t.columns[1].width = Inches(0.9)
    eq_cell, num_cell = t.cell(0, 0), t.cell(0, 1)
    remove_cell_borders(eq_cell)
    remove_cell_borders(num_cell)

    eq_p = eq_cell.paragraphs[0]
    eq_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    M.add_display_equation(eq_p, builder())

    num_p = num_cell.paragraphs[0]
    num_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = num_p.add_run(f"({eq_number})")
    r.font.size = Pt(10)
    doc.add_paragraph()


# ════════════════════════════════════════════════════════════════════════
#                       SECTION 1 — EXECUTIVE SUMMARY
# ════════════════════════════════════════════════════════════════════════

def add_section_1(doc):
    add_section_heading(doc, 1, "Executive Summary")

    add_paragraph(doc,
        "Market Dashboard Auto is a fully-automated, free-data macro-market "
        "intelligence pipeline that runs nightly on GitHub Actions and "
        "produces, for each trading day: a snapshot of approximately three "
        "hundred and ninety financial instruments across all major asset "
        "classes; weekly historical price series back to 1950; raw "
        "macro-economic data covering twelve economies and ten public-source "
        "providers back to 1947; and a derived layer of ninety-two composite "
        "indicators, each carrying a rolling z-score, a regime classification, "
        "a forward-regime signal, and a z-score trajectory diagnostic. "
        "Outputs land in Google Sheets, in version-controlled CSV files, and "
        "in an interactive HTML explorer. The pipeline has been operating in "
        "production since the consolidation of its multi-source coordinator "
        "in April 2026, and it is the substrate on which downstream "
        "analytical work — including regime-based asset allocation research — "
        "is being built."
    )

    add_paragraph(doc,
        "The design centres on a single architectural rule: every identifier "
        "the pipeline fetches lives in a CSV registry rather than in Python "
        "code. This rule is enforced by an integrated daily audit covering "
        "fetch outcomes, schema drift across three history–library pairs, "
        "value-change staleness against per-frequency tolerances, and "
        "history preservation under retroactive source-side truncation. "
        "Operational scaffolding — a writeback step that retires dead "
        "tickers automatically after a fourteen-day streak, a perpetual "
        "GitHub Issue thread for the daily heartbeat, and an idempotent "
        "Sheets-tab cleanup mechanism — removes the operator from the "
        "daily loop entirely."
    )

    # Key-facts panel
    add_paragraph(doc, "Key facts at a glance:", bold=True, size=10.5,
                  space_after=2)

    facts = [
        ("Instruments tracked",            "~390 across 8 asset classes"),
        ("Macro series ingested",          "~150 across 12 economies"),
        ("Composite indicators computed",  "92 (90 Leading, 2 Coincident)"),
        ("Free public data sources",       "10 (FRED, OECD, World Bank, IMF, "
                                           "DB.nomics, ifo, BoE, ECB, BoJ, e-Stat)"),
        ("Code base",                      "~9,400 lines of Python across "
                                           "7 top-level modules + 12-module sources/ package"),
        ("Earliest historical data",       "1947 (FRED), 1950 (yfinance), "
                                           "1991 (ifo), 1955 (e-Stat)"),
        ("Daily run wall-clock",           "12–15 minutes end-to-end"),
        ("Operational status",             "Production, ~270 successful daily runs"),
        ("Operator burden",                "Zero per-day; weekly review of GitHub Issue thread"),
    ]
    add_shaded_table(doc,
        headers=["Item", "Value"],
        rows=facts,
        col_widths=[Inches(2.2), Inches(4.3)],
    )

    add_paragraph(doc,
        "This report describes the system as it stands today. Section 2 "
        "frames the problem the project addresses and the constraints "
        "imposed by the free-data stance. Section 3 presents the end-to-end "
        "system in a single data-flow view. Sections 4 and 5 cover the data "
        "architecture and the design principles that make the system "
        "durable. Section 6 documents the composite-indicator methodology "
        "in detail, including six worked examples spanning the indicator "
        "families. Section 7 covers regime classification. Section 8 "
        "describes the operational scaffolding. Sections 9 and 10 cover "
        "the user-facing artefacts and the integration surface. Sections "
        "11 to 13 record current coverage, accepted gaps, and the residual "
        "limitations the system must carry. The mathematical notation is "
        "consolidated in Appendix A; references are in Appendix B."
    )


# ════════════════════════════════════════════════════════════════════════
#                  SECTION 2 — PROBLEM STATEMENT & MOTIVATION
# ════════════════════════════════════════════════════════════════════════

def add_section_2(doc):
    add_section_heading(doc, 2, "Problem Statement & Motivation")

    add_subsection_heading(doc, "2.1", "The macro-market analyst's daily problem")

    add_paragraph(doc,
        "Interpretation of current market conditions requires consolidated, "
        "cross-asset, cross-region context. A practitioner must be able to "
        "see, in a single workspace, where equity rotation is pointing, "
        "what the credit complex is signalling, whether the yield curve "
        "agrees, how volatility regimes are evolving, what the major "
        "macro-economic releases are saying, and whether the supporting "
        "evidence is strengthening or weakening. Commercial platforms — "
        "Bloomberg, FactSet, Refinitiv — assemble this picture at a "
        "professional-licence cost typically in the range of twenty to "
        "thirty thousand pounds sterling per seat per annum. For an "
        "individual practitioner or a small research team, that cost is "
        "prohibitive."
    )

    add_paragraph(doc,
        "The free-data alternative is fragmented. Each major statistical "
        "agency publishes data through its own API, with its own schema, "
        "rate-limit profile, error semantics, and cadence. The Federal "
        "Reserve's FRED service is rich and well-engineered but covers "
        "only United States macro statistics in depth. The OECD's SDMX "
        "interface offers cross-country coverage at the cost of a "
        "verbose query convention and tight rate limits. The Bank of "
        "Japan, the Bank of England, the European Central Bank, the "
        "Statistics Bureau of Japan, the ifo Institute and DB.nomics "
        "each speak different dialects again. yfinance, the de facto "
        "free price feed for non-commercial users, has its own pattern "
        "of brittle behaviour around delisted instruments, regional "
        "exchanges, and currency conventions. None of these sources is "
        "individually sufficient; together, they require careful "
        "integration to be reliable."
    )

    add_subsection_heading(doc, "2.2", "Constraints")

    add_paragraph(doc,
        "Three constraints follow from the practitioner setting and have "
        "shaped every subsequent design decision:"
    )

    add_bullet(doc,
        "Free, openly accessible sources only. The pipeline accepts no paid "
        "feed and no scraped, terms-of-service-violating route. Where a "
        "desired indicator is available only behind a paywall — Caixin "
        "China Manufacturing PMI, S&P Global PMI series, ICE corporate "
        "bond indices in their full historical depth — that indicator is "
        "either replaced with a free proxy or recorded as an accepted gap."
    )
    add_bullet(doc,
        "Daily refresh discipline without operator intervention. The "
        "pipeline must execute every day, recover from transient errors "
        "automatically, surface persistent errors through a non-blocking "
        "channel, and continue producing partial output even when an "
        "individual phase fails. The operator must not be required to "
        "log in to keep the pipeline alive."
    )
    add_bullet(doc,
        "Multi-source ingestion under a single architectural discipline. "
        "Without enforced uniformity across sources, the integration cost "
        "of each new provider rises rather than falls. This is the design "
        "pressure that produced the registry-first architecture documented "
        "in Section 4."
    )

    add_subsection_heading(doc, "2.3", "Resolution approach")

    add_paragraph(doc,
        "The free-source constraint is honoured by enumeration: every "
        "fetched identifier is registered in one of the source-of-truth "
        "CSV files in the data/ directory, and that registry is the only "
        "mechanism by which a new series enters the pipeline. Any "
        "reaching for a string literal in Python code that resembles a "
        "fetched identifier is, by adopted rule, prohibited. The rule "
        "originated in response to two avoidable refactors caused by "
        "exactly that drift; it is now enforced both socially (a "
        "pre-commit checklist for collaborators) and technically "
        "(the daily audit's static-checks section flags any column in a "
        "history file that does not trace to a registry row)."
    )

    add_paragraph(doc,
        "Reliability under daily operation is achieved through phase "
        "isolation and per-series error containment. Each runtime phase "
        "is wrapped in a module-level exception handler such that a "
        "failure in any later phase cannot affect outputs already "
        "written by earlier phases. Inside each phase, every individual "
        "ticker, series, or indicator computation is similarly "
        "wrapped — a single bad observation never propagates to the "
        "rest of the output. These two patterns, layered, make partial "
        "success the default behaviour and full failure the exception."
    )

    add_paragraph(doc,
        "Operator removal is achieved through GitHub Actions for the "
        "execution channel, automatic Git commit-and-push of the "
        "outputs for the persistence channel, and a perpetual GitHub "
        "Issue thread for the notification channel. Every daily run "
        "posts a single Markdown comment to the same issue, with the "
        "first line summarising the result as either ALL CLEAN or "
        "as a count of issues. GitHub's native notification mechanism "
        "delivers this to the operator's email; no SMTP infrastructure "
        "is required."
    )

    add_subsection_heading(doc, "2.4", "Scope")

    add_paragraph(doc,
        "Within scope are: (a) ingestion and curation of the data layer, "
        "(b) computation of the composite-indicator layer including "
        "z-score, regime, forward-regime, and trajectory semantics, (c) "
        "the operational scaffolding required for daily reliability, and "
        "(d) the user-facing presentation layer (Google Sheets tabs and "
        "the interactive HTML explorer). Out of scope at this stage are "
        "alpha generation or signal-following execution, individual-stock "
        "research below the index level, and any analysis requiring "
        "intra-day cadence. Forward-looking analytical work — including "
        "regime-based asset allocation, back-testing, and portfolio "
        "construction — is built on top of this substrate but is not "
        "the subject of this report."
    )


# ════════════════════════════════════════════════════════════════════════
#                       SECTION 3 — SYSTEM OVERVIEW
# ════════════════════════════════════════════════════════════════════════

def add_section_3(doc):
    add_section_heading(doc, 3, "System Overview")

    add_paragraph(doc,
        "The pipeline is a single waterfall executed once per day. A "
        "GitHub Actions cron job at 00:34 UTC invokes the master "
        "orchestrator, which in turn chains in the historical, "
        "macro-economic, composite-indicator, and explorer-rebuild "
        "phases. After the data phases complete, an integrated audit "
        "runs and a writeback step adjusts the instrument library "
        "based on persistent dead-ticker streaks. Every step's output "
        "is committed back to the repository. The end-to-end wall-clock "
        "runtime is between twelve and fifteen minutes."
    )

    add_subsection_heading(doc, "3.1", "Daily execution flow")

    add_paragraph(doc,
        "The diagram below is the full daily flow. Each stage's exception "
        "handler ensures that downstream failures cannot reach back to "
        "corrupt the outputs of earlier stages."
    )

    add_dataflow_diagram(doc, [
        "GitHub Actions cron — 00:34 UTC",
        "fetch_data.py  •  Simple + Comp pipelines",
        "fetch_hist.py  •  Comp weekly history (1950→)",
        "fetch_macro_economic.py  •  Phase ME (10-source unified registry)",
        "compute_macro_market.py  •  Phase E (92 composite indicators)",
        "docs/build_html.py  •  Indicator Explorer rebuild",
        "data_audit.py  •  Daily integrated audit (4 sections)",
        "audit_writeback.py  •  Library writeback (dead-ticker streaks)",
        "git commit + push  •  Sheets push  •  GitHub Issue comment",
    ])

    add_subsection_heading(doc, "3.2", "Runtime phases")

    add_paragraph(doc,
        "The phase nomenclature reflects the chronological order in which "
        "the project was built rather than the runtime order. Phases A, "
        "B, C and D — the per-source US-FRED, surveys, international, "
        "and business-survey coordinators respectively — were "
        "consolidated into a single Phase ME (Macro-Economic) "
        "coordinator on 23 April 2026; their tabs are now retired and "
        "are swept from the Google Sheets workspace on every run. The "
        "current phase inventory is:"
    )

    rows = [
        ("Simple Pipeline",
         "fetch_data.py",
         "market_data, sentiment_data",
         "Production (frozen)"),
        ("Comp Pipeline",
         "fetch_data.py + fetch_hist.py",
         "market_data_comp, market_data_comp_hist",
         "Production"),
        ("Phase ME — Macro-Economic",
         "fetch_macro_economic.py + sources/*.py",
         "macro_economic, macro_economic_hist",
         "Production"),
        ("Phase E — Macro-Market Indicators",
         "compute_macro_market.py",
         "macro_market, macro_market_hist",
         "Production"),
        ("Phase F — Calculated Fields",
         "absorbed into compute_macro_market.py",
         "(see Phase E outputs)",
         "Mostly absorbed"),
        ("Phase G — Sheets Export Audit",
         "library_utils.py SHEETS_* constants",
         "(no separate output)",
         "Done"),
        ("Phase H — Daily Integrated Audit",
         "data_audit.py + audit_writeback.py",
         "data_audit.txt, audit_comment.md",
         "Done"),
    ]
    add_shaded_table(doc,
        headers=["Phase", "Module(s)", "Output tabs / artefacts", "Status"],
        rows=rows,
        col_widths=[Inches(1.7), Inches(2.0), Inches(1.8), Inches(1.0)],
    )

    add_subsection_heading(doc, "3.3", "Outputs")

    add_paragraph(doc,
        "The pipeline writes seven active Google Sheets tabs, each "
        "mirrored as a CSV in the data/ directory of the repository. "
        "A retired-tab frozenset is swept on every run so that "
        "decommissioned tabs cannot accumulate. In parallel, the "
        "indicator-explorer rebuild produces a self-contained HTML "
        "page and an embedded JavaScript bundle of market data. "
        "All of these artefacts are committed back to the main "
        "branch with a timestamped message; the explorer is "
        "additionally published to GitHub Pages."
    )

    rows = [
        ("market_data",            "Snapshot, ~70 instruments",
         "Simple pipeline; consumed by downstream trigger.py"),
        ("market_data_comp",       "Snapshot, ~390 instruments",
         "Comp pipeline; full instrument library"),
        ("market_data_comp_hist",  "Weekly history from 1950",
         "Friday-spine alignment; 10 metadata prefix rows"),
        ("macro_economic",         "Long-form snapshot",
         "Unified raw-macro layer across all 10 sources"),
        ("macro_economic_hist",    "Wide-form weekly history from 1947",
         "14 metadata prefix rows + Friday spine"),
        ("macro_market",           "92 indicators, snapshot",
         "Includes z-score, regime, fwd_regime, trajectory diagnostics"),
        ("macro_market_hist",      "Weekly indicator history from 2000",
         "raw, zscore, regime, fwd_regime per indicator"),
    ]
    add_shaded_table(doc,
        headers=["Tab / CSV", "Shape", "Contents"],
        rows=rows,
        col_widths=[Inches(1.8), Inches(2.1), Inches(2.6)],
    )

    add_callout(doc,
        "Why a Friday spine?",
        "Macro releases arrive on heterogeneous cadences (daily, weekly, "
        "monthly, quarterly, annual). Aligning every series to a single "
        "weekly Friday-close index allows cross-series analysis and "
        "z-score computation without per-pair date-alignment logic. "
        "Forward-fill into the Friday slots is acceptable because the "
        "downstream value-change staleness audit (Section 8) detects "
        "any series that has stopped moving."
    )


# ════════════════════════════════════════════════════════════════════════
#               SECTION 4 — DATA ARCHITECTURE & SOURCE CATALOGUE
# ════════════════════════════════════════════════════════════════════════

def add_section_4(doc):
    add_section_heading(doc, 4, "Data Architecture & Source Catalogue")

    add_subsection_heading(doc, "4.1", "The single architectural rule")

    add_paragraph(doc,
        "The project's dominant design rule is this: every identifier the "
        "pipeline fetches must live in a CSV registry under data/, never "
        "in Python source. The motivation for the rule is empirical. "
        "Two earlier refactors had to chase hardcoded identifiers out of "
        "the codebase — the indicator-metadata Python dictionary into a "
        "registry CSV in April 2026, and the per-source coordinators into "
        "a unified coordinator one week later. Each refactor cost "
        "engineering time that would not have been incurred had the "
        "identifiers lived in their proper home from the outset."
    )

    add_paragraph(doc,
        "The rule applies to: FRED series identifiers, DB.nomics series "
        "paths, OECD SDMX dataflow and dimension keys, World Bank and IMF "
        "indicator codes, ifo Excel sheet and column locations, ECB and "
        "BoE series codes, BoJ time-series codes, e-Stat statsDataIds, "
        "yfinance tickers, and any URL fragment that selects a specific "
        "dataset. It does not apply to: API base URLs, computation "
        "parameters such as the z-score window, internal column-name "
        "conventions, or calculator wiring (which series each calculator "
        "consumes), since those are logic rather than registry."
    )

    add_callout(doc,
        "Architectural invariant",
        "If a change adds, removes, renames, or substitutes a fetched "
        "identifier, the only file edited is the appropriate "
        "data/macro_library_*.csv (or index_library.csv / "
        "macro_indicator_library.csv depending on the layer). No "
        "exceptions. This invariant is verified daily by the audit's "
        "registry-drift static check."
    )

    add_subsection_heading(doc, "4.2", "The data-layer registry")

    add_paragraph(doc,
        "Fourteen CSV files together constitute the data-layer registry. "
        "They are read at process startup, never written by the runtime "
        "pipeline, and version-controlled in the same repository as the "
        "code. Adding or removing a series is a one-CSV-row commit; "
        "renaming a series is a one-CSV-cell commit."
    )

    rows = [
        ("index_library.csv",            "~401",
         "Comp pipeline tickers (yfinance + FRED bond indices)"),
        ("macro_library_countries.csv",  "12",
         "Country codes + per-source code mappings (WB, IMF, OECD)"),
        ("macro_library_fred.csv",       "~82",
         "FRED series IDs (US + international)"),
        ("macro_library_oecd.csv",       "3",
         "OECD SDMX dataflow + dimension keys"),
        ("macro_library_worldbank.csv",  "1",
         "World Bank WDI indicator codes (CPI YoY)"),
        ("macro_library_imf.csv",        "1",
         "IMF DataMapper indicator codes (real GDP growth)"),
        ("macro_library_dbnomics.csv",   "13",
         "DB.nomics series paths (Eurostat, ISM, IMF/IFS fallbacks)"),
        ("macro_library_ifo.csv",        "26",
         "ifo workbook sheet/column locations"),
        ("macro_library_boe.csv",        "7",
         "BoE IADB series (Bank Rate, SONIA, gilt par/zero curves)"),
        ("macro_library_ecb.csv",        "3",
         "ECB Data Portal SDMX keys (deposit rate, AAA yield curve)"),
        ("macro_library_boj.csv",        "2",
         "BoJ time-series codes (policy rate, Tankan large mfg DI)"),
        ("macro_library_estat.csv",      "1",
         "e-Stat statsDataIds (METI Indices of Industrial Production)"),
        ("source_fallbacks.csv",         "9",
         "Per-indicator T0/T1/T2/T3 fallback chain (documentation-only)"),
        ("macro_indicator_library.csv",  "92",
         "Phase E composite indicator definitions"),
    ]
    add_shaded_table(doc,
        headers=["Registry file", "Rows", "Contents"],
        rows=rows,
        col_widths=[Inches(2.4), Inches(0.6), Inches(3.5)],
    )

    add_subsection_heading(doc, "4.3", "Source catalogue")

    add_paragraph(doc,
        "Ten free public sources currently contribute to the data layer. "
        "Each has its own access protocol, its own rate-limit envelope, "
        "and its own pattern of edge-case behaviour; the per-source "
        "modules in the sources/ package encapsulate these differences "
        "so that the upper layers can treat the data uniformly."
    )

    rows = [
        ("yfinance",     "Yahoo Finance",
         "~390 instruments — equities, ETFs, FX, commodities, crypto, vol",
         "No key"),
        ("FRED",         "St. Louis Fed",
         "~85 series across yields, inflation, labour, credit, surveys",
         "Free key"),
        ("OECD",         "OECD SDMX",
         "Composite Leading Indicator, unemployment, 3-month interbank",
         "No key"),
        ("World Bank",   "World Bank WDI",
         "CPI YoY across 11 economies",
         "No key"),
        ("IMF",          "IMF DataMapper",
         "Real GDP Growth (annual WEO including projections)",
         "No key"),
        ("DB.nomics",    "DB.nomics REST",
         "Eurostat surveys, ISM PMIs, IMF/IFS fallback rates",
         "No key"),
        ("ifo",          "ifo Institute",
         "26 German business-survey series (1991→) via Excel workbook",
         "No key"),
        ("BoE",          "Bank of England IADB",
         "Bank Rate, SONIA, gilt par + zero-coupon yields",
         "No key"),
        ("ECB",          "ECB Data Portal",
         "Deposit Facility Rate, AAA yield curve points",
         "No key"),
        ("BoJ",          "Bank of Japan Time-Series",
         "Policy Rate, Tankan Large Manufacturer DI",
         "No key"),
        ("e-Stat",       "Statistics Bureau Japan",
         "METI Indices of Industrial Production (1955→)",
         "Free App ID"),
    ]
    add_shaded_table(doc,
        headers=["Source", "Provider", "Coverage", "Auth"],
        rows=rows,
        col_widths=[Inches(0.9), Inches(1.5), Inches(3.3), Inches(0.7)],
    )

    add_subsection_heading(doc, "4.4", "Country and currency coverage")

    add_paragraph(doc,
        "The country registry covers twelve economies: the United States, "
        "United Kingdom, Germany, France, Italy, Japan, China, Australia, "
        "Canada, Switzerland, the Eurozone aggregate (EA19/EA20 depending "
        "on the source's convention), and India (added April 2026 to "
        "support the India 10-year bond yield series). The registry is "
        "the single source of truth: the World Bank uses code EMU for "
        "the Eurozone and the IMF DataMapper uses code EURO; both "
        "mappings live in macro_library_countries.csv rather than in "
        "Python."
    )

    add_paragraph(doc,
        "Foreign-exchange coverage spans eighteen currencies, of which "
        "fifteen are indirect-quote (i.e. expressed as foreign currency "
        "per US dollar — JPY, CNY, CAD, INR, KRW, HKD, BRL, TWD, MXN, "
        "ZAR, TRY, IDR, RUB, SAR) and three are direct-quote (GBP, EUR, "
        "AUD). For each non-USD instrument the comp pipeline computes a "
        "USD-adjusted return alongside the local-currency return. The "
        "identity used is:"
    )

    add_eq_display(doc, EQ.usd_return, eq_number="4.1")

    add_paragraph(doc,
        "Indirect-quote currencies require inversion of the FX rate "
        "before applying the identity; the inversion is automatic, "
        "driven by membership in the COMP_FCY_PER_USD set in "
        "library_utils.py."
    )

    add_paragraph(doc,
        "A second pre-processing rule applies to UK-listed instruments. "
        "London Stock Exchange tickers (those ending in .L) report "
        "prices in pence (GBp) rather than pounds (GBP) for some "
        "instruments and not others. Rather than maintaining a "
        "hardcoded list of pence-denominated tickers, the pipeline "
        "applies the dynamic correction:"
    )

    add_eq_display(doc, EQ.pence_correction, eq_number="4.2")

    add_paragraph(doc,
        "The threshold of fifty is empirically chosen: no genuine "
        "GBP-denominated UK security has had a median price below "
        "fifty pounds across the available history, while every "
        "pence-denominated security has."
    )

    add_subsection_heading(doc, "4.5", "Source-fallback chain")

    add_paragraph(doc,
        "Because nine FRED series carrying internationally-mirrored "
        "macro data have stopped updating (the OECD-mirror series for "
        "the Japanese policy rate, the Chinese policy rate, the UK "
        "Bank Rate, Eurozone HICP, German industrial production and "
        "others), the pipeline carries a per-indicator fallback "
        "registry in source_fallbacks.csv. Each row records the canonical "
        "tier-zero source for an indicator together with up to three "
        "fallback sources (T1, T2, T3). The runtime currently realises "
        "the chain implicitly through the read order in the unified "
        "coordinator — later sources overwrite earlier sources at the "
        "column level. Of the nine forcing-function rows, seven have "
        "been resolved through tier-one and tier-two fallbacks (DB.nomics "
        "IMF/IFS, Eurostat, the BoE IADB, the ECB Data Portal, the BoJ "
        "Time-Series API, and e-Stat); two remain accepted gaps because "
        "the underlying Chinese statistical agencies publish no free "
        "programmatic interface."
    )


# ════════════════════════════════════════════════════════════════════════
#                  SECTION 5 — PIPELINE DESIGN PRINCIPLES
# ════════════════════════════════════════════════════════════════════════

def add_section_5(doc):
    add_section_heading(doc, 5, "Pipeline Design Principles")

    add_paragraph(doc,
        "Nine recurring design patterns are used across the codebase. "
        "They are documented here once because each pattern appears in "
        "multiple modules; pattern-by-pattern documentation in each "
        "module would duplicate without adding clarity."
    )

    # 5.1 Phase isolation
    add_subsection_heading(doc, "5.1", "Phase isolation")

    add_paragraph(doc,
        "Every runtime phase after the master orchestrator's main "
        "function is wrapped in a module-level try/except block that "
        "catches every exception, logs it, and proceeds to the next "
        "phase. This pattern is the load-bearing reliability mechanism "
        "of the pipeline. If the macro-economic phase crashes — say, "
        "because OECD SDMX is briefly unavailable — the simple "
        "pipeline, the comp pipeline, and the comp historical phase "
        "have already completed and their outputs are already on disk. "
        "The audit subsequently surfaces the macro-economic failure, "
        "but no data the operator depends on has been lost."
    )

    # 5.2 Per-series try/except
    add_subsection_heading(doc, "5.2", "Per-series exception containment")

    add_paragraph(doc,
        "Inside each phase, every individual fetch — one ticker, one "
        "FRED series, one OECD country fan-out, one indicator "
        "computation — is itself wrapped in a try/except block that "
        "logs the failure and continues. A single bad series never "
        "kills the rest of the output. This is the difference between "
        "‘the pipeline failed’ and ‘the pipeline succeeded with twenty "
        "rows missing’; the latter is a strictly more useful state "
        "because the missing rows are visible in the audit and can be "
        "remediated, while preserved rows continue to inform analysis."
    )

    # 5.3 Friday spine
    add_subsection_heading(doc, "5.3", "Friday-spine alignment")

    add_paragraph(doc,
        "All historical data is aligned to a weekly index of Friday "
        "dates. For a series sampled at any cadence, the value at "
        "Friday t is taken as the most recent observation on or before "
        "t, with forward-fill into Friday slots where the source has "
        "not yet released. Formally:"
    )

    add_eq_display(doc, EQ.friday_spine, eq_number="5.1")

    add_paragraph(doc,
        "The Friday convention is chosen because end-of-week is the "
        "least ambiguous market data point for cross-asset analysis. "
        "The forward-fill is acceptable in conjunction with the "
        "value-change staleness audit (Section 8): any series that "
        "has stopped moving is detected and flagged regardless of "
        "whether its forward-filled cells continue to populate."
    )

    # 5.4 Metadata prefix rows
    add_subsection_heading(doc, "5.4", "Metadata prefix rows")

    add_paragraph(doc,
        "History tabs in Google Sheets carry metadata rows above the "
        "data block. The macro-economic history carries fourteen "
        "prefix rows (Column ID, Series ID, Source, Indicator, Country, "
        "Country Name, Region, Category, Subcategory, Concept, "
        "cycle_timing, Units, Frequency, Last Updated). The market-data "
        "comp history carries ten prefix rows. These rows are visible "
        "to a human reader of the spreadsheet, support the explorer's "
        "by-concept and by-region grouping, and are consistently "
        "skipped by every code path that reads the history file via "
        "an explicit header offset."
    )

    # 5.5 Library-driven configuration
    add_subsection_heading(doc, "5.5", "Library-driven configuration")

    add_paragraph(doc,
        "Beyond the registry rule of Section 4.1, several "
        "configuration knobs that would conventionally live in code "
        "have been moved to CSV columns. The simple-pipeline "
        "instrument selection is a boolean column on the master "
        "library. The validation status of each ticker — CONFIRMED, "
        "PENDING, UNAVAILABLE — is a column. Per-row overrides on "
        "freshness tolerances are columns on the per-source library "
        "files. The result is that operator interventions — disabling "
        "a broken series, widening a tolerance for a slow publisher, "
        "swapping in a proxy ticker — are CSV edits rather than "
        "code commits."
    )

    # 5.6 Diff-check CSV commits
    add_subsection_heading(doc, "5.6", "Diff-check CSV commits")

    add_paragraph(doc,
        "Output CSV files are only committed back to git when their "
        "content has actually changed. This avoids a noisy commit "
        "history during weekends and holidays when markets are closed "
        "and series have not moved, while still committing every "
        "weekday's genuine update. The diff check is byte-level after "
        "a deterministic sort and serialisation, so it is robust to "
        "ordering instabilities in upstream APIs."
    )

    # 5.7 Sheets write pattern
    add_subsection_heading(doc, "5.7", "Sheets write pattern")

    add_paragraph(doc,
        "All writers to Google Sheets follow a five-step pattern: "
        "check the target tab against a protected-tab frozenset and "
        "abort if matched, ensure the tab exists (creating it if "
        "necessary), clear the existing range, write the new data, "
        "and finally sweep a separate legacy-tab frozenset on the "
        "way out so retired tabs cannot accumulate. The two frozensets "
        "— SHEETS_PROTECTED_TABS and SHEETS_LEGACY_TABS_TO_DELETE — "
        "are defined once in library_utils.py and imported by every "
        "writer. Adding or retiring a tab is a one-line edit there; "
        "no other writer needs to know."
    )

    # 5.8 Rate limiting
    add_subsection_heading(doc, "5.8", "Rate limiting and exponential backoff")

    add_paragraph(doc,
        "Every external HTTP call is rate-limited with a per-source "
        "base delay and retried with exponential backoff on transient "
        "failures (HTTP 429 or 5xx). The delays and retry budgets are "
        "tuned per source to its published or empirically-observed "
        "rate envelope:"
    )

    rows = [
        ("yfinance",   "0.3 s",   "—",                            "3"),
        ("FRED",       "0.6 s",   "2, 4, 8, 16, 32 s",            "5"),
        ("OECD",       "4.0 s",   "2, 4, 8, 16, 32 s",            "5"),
        ("World Bank", "1.0 s",   "2, 4, 8, 16, 32 s",            "5"),
        ("IMF",        "1.0 s",   "2, 4, 8, 16, 32 s",            "5"),
        ("ECB",        "0.6 s",   "2, 4, 8, 16 s",                "3"),
        ("BoE",        "0.6 s",   "2, 4, 8, 16 s",                "3"),
        ("BoJ",        "0.6 s",   "2, 4, 8, 16 s",                "3"),
        ("e-Stat",     "0.6 s",   "2, 4, 8, 16 s",                "3"),
    ]
    add_shaded_table(doc,
        headers=["Source", "Base delay", "Backoff schedule", "Max retries"],
        rows=rows,
        col_widths=[Inches(1.3), Inches(1.1), Inches(2.0), Inches(1.2)],
    )

    # 5.9 History preservation
    add_subsection_heading(doc, "5.9", "History preservation under source truncation")

    add_paragraph(doc,
        "Source-side history can shrink retroactively. The cleanest "
        "example is the ICE Data licence change of April 2026, which "
        "obliged FRED to truncate its redistributed ICE BofA spread "
        "series — including BAMLH0A0HYM2, BAMLC0A0CM and "
        "BAMLHE00EHYIOAS — to a rolling three-year window. Twenty "
        "or more years of pre-2023 spread data disappeared from the "
        "FRED side. Without intervention, the next nightly fetch "
        "would have overwritten the local history with the truncated "
        "window, losing the historical depth on which the rolling "
        "z-score depends."
    )

    add_paragraph(doc,
        "The mitigation is architectural. For every primary history "
        "file the pipeline writes, an append-only sister file "
        "captures rows that pre-date the current source-side window. "
        "The detection logic operates per column rather than per "
        "row: a rolling-window source can keep row count constant "
        "while the earliest non-null date walks forward each cycle, "
        "so the test is whether a column's earliest non-null date "
        "in the new fetch is later than the earliest non-null date "
        "previously stored. If so, the rows about to disappear are "
        "appended to the sister file, deduplicated by date, before "
        "the live file is rewritten with the new window. Read paths "
        "transparently union the live and sister files, with the "
        "live file winning where it has a non-null observation."
    )

    add_callout(doc,
        "Out of scope",
        "This rule preserves history that the pipeline already has. "
        "It does not back-fill history that was never captured. Filling "
        "a pre-installation gap would require either a paid ICE Data "
        "subscription or an alternative archive — neither is currently "
        "in scope."
    )


# ════════════════════════════════════════════════════════════════════════
#               STEP 2 PROBE (kept at tail until Step 6 polish)
# ════════════════════════════════════════════════════════════════════════

def add_step2_probe(doc):
    """Equation typography sign-off — every catalogued equation, in order."""
    doc.add_page_break()
    doc.add_heading("Appendix Z — Equation library probe (interim)", level=1)

    add_paragraph(doc,
        "This appendix renders every equation in the report's library as a "
        "centred display equation, for typography review. It will be "
        "removed in Step 6 once equations have been individually signed "
        "off in their final positions in the body. Reviewer to confirm "
        "italic-symbol / upright-label conventions, piecewise legibility, "
        "and operator spacing.",
        italic=True,
    )

    p = doc.add_paragraph()
    r = p.add_run(f"Equation count: {len(EQ.CATALOGUE)}.")
    r.italic = True

    for label, builder, description in EQ.CATALOGUE:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after  = Pt(2)
        r = p.add_run(label)
        r.bold = True
        r.font.size = Pt(11)

        if description:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            r = p.add_run(description)
            r.italic = True
            r.font.size = Pt(9.5)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after  = Pt(8)
        M.add_display_equation(p, builder())


# ── orchestration ───────────────────────────────────────────────────────

def main():
    doc = Document()
    setup_document(doc)
    add_title_page(doc)

    # Body — sections authored to date
    add_section_1(doc)
    add_section_2(doc)
    add_section_3(doc)
    add_section_4(doc)
    add_section_5(doc)

    # Interim equation probe (removed in Step 6)
    add_step2_probe(doc)

    out_dir  = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, OUT_FILENAME)
    doc.save(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
