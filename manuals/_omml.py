"""
OMML (Office Math Markup Language) primitives + injection helpers for
python-docx.

python-docx has no native equation support. Word equations are stored as
OMML XML inside the document body. This module provides:

  1. small XML-string builders for common math constructs (subscript,
     superscript, fraction, parenthesis, etc.)
  2. injection helpers that take a paragraph and append a parsed OMML
     element so Word recognises it as a native, editable equation.

Building blocks return bare OMML XML strings (no namespace declarations).
The two injection helpers (`add_inline_equation`, `add_display_equation`)
declare the `m:` namespace once on the outermost element and parse the
result via `docx.oxml.parse_xml`.

Variable convention: single-letter math symbols (`r`, `x`, `t`) render
italic by default per OMML rules. Multi-character labels (e.g. `USD`,
`local`, `FX`) should be passed with `plain=True` so they render upright,
matching mathematical typography.
"""

from docx.oxml import parse_xml

OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


# ── primitive builders ───────────────────────────────────────────────────

def _txt(text):
    """Escape XML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def run(text, plain=False):
    """A single math text run.

    plain=True applies the upright (non-italic) style to multi-letter
    labels and operators. By default OMML italicises letter content.
    """
    safe = _txt(text)
    if plain:
        return (
            '<m:r>'
            '<m:rPr><m:sty m:val="p"/></m:rPr>'
            f'<m:t>{safe}</m:t>'
            '</m:r>'
        )
    return f'<m:r><m:t>{safe}</m:t></m:r>'


def sub(base, subscript):
    """base_{subscript}"""
    return (
        '<m:sSub>'
        f'<m:e>{base}</m:e>'
        f'<m:sub>{subscript}</m:sub>'
        '</m:sSub>'
    )


def sup(base, superscript):
    """base^{superscript}"""
    return (
        '<m:sSup>'
        f'<m:e>{base}</m:e>'
        f'<m:sup>{superscript}</m:sup>'
        '</m:sSup>'
    )


def subsup(base, subscript, superscript):
    """base_{subscript}^{superscript}"""
    return (
        '<m:sSubSup>'
        f'<m:e>{base}</m:e>'
        f'<m:sub>{subscript}</m:sub>'
        f'<m:sup>{superscript}</m:sup>'
        '</m:sSubSup>'
    )


def frac(num, den):
    """num / den (built-up fraction)"""
    return (
        '<m:f>'
        f'<m:num>{num}</m:num>'
        f'<m:den>{den}</m:den>'
        '</m:f>'
    )


def paren(inner, left="(", right=")"):
    """(inner) — delimited expression. left/right may be other delimiters."""
    return (
        '<m:d>'
        '<m:dPr>'
        f'<m:begChr m:val="{_txt(left)}"/>'
        f'<m:endChr m:val="{_txt(right)}"/>'
        '</m:dPr>'
        f'<m:e>{inner}</m:e>'
        '</m:d>'
    )


def abs_(inner):
    """|inner|"""
    return paren(inner, left="|", right="|")


def sqrt(inner):
    return f'<m:rad><m:deg/><m:e>{inner}</m:e></m:rad>'


def sum_over(idx, lo, hi, body):
    """Sum from lo to hi of body. idx unused but kept for future indexing."""
    return (
        '<m:nary>'
        '<m:naryPr>'
        '<m:chr m:val="∑"/>'
        '<m:limLoc m:val="undOvr"/>'
        '</m:naryPr>'
        f'<m:sub>{lo}</m:sub>'
        f'<m:sup>{hi}</m:sup>'
        f'<m:e>{body}</m:e>'
        '</m:nary>'
    )


def func(name, arg, plain_name=True):
    """Named function: log(x), exp(x), etc. Function name rendered upright."""
    return (
        '<m:func>'
        f'<m:fName>{run(name, plain=plain_name)}</m:fName>'
        f'<m:e>{arg}</m:e>'
        '</m:func>'
    )


def oMath(*parts):
    """Inline math container."""
    return '<m:oMath>' + ''.join(parts) + '</m:oMath>'


# ── injection helpers ────────────────────────────────────────────────────

def _inject_ns(xml, root_tag):
    """Add xmlns:m declaration to the named root tag exactly once."""
    return xml.replace(
        f'<{root_tag}>',
        f'<{root_tag} xmlns:m="{OMML_NS}">',
        1,
    )


def add_inline_equation(paragraph, omath_xml):
    """Append a `<m:oMath>` element to `paragraph` as an inline equation.

    `omath_xml` must be the output of `oMath(...)` — i.e. start with
    `<m:oMath>`. The m: namespace is declared automatically.
    """
    wrapped = _inject_ns(omath_xml, "m:oMath")
    paragraph._p.append(parse_xml(wrapped))


def add_display_equation(paragraph, omath_xml):
    """Append an `<m:oMathPara><m:oMath>...</m:oMath></m:oMathPara>` block
    to `paragraph` as a display (block-level) equation.

    `omath_xml` is the output of `oMath(...)`. The wrapper and namespace
    are added here.
    """
    wrapped = (
        f'<m:oMathPara xmlns:m="{OMML_NS}">'
        f'{omath_xml}'
        '</m:oMathPara>'
    )
    paragraph._p.append(parse_xml(wrapped))
