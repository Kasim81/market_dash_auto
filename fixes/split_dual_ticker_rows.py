"""
Remediation: split dual-ticker rows (FEZ, ASHR)
===============================================
Audit follow-up (2026-07-14, per Kas): FEZ and ASHR were single `yfinance PR`
library rows that each carried BOTH a foreign *index* ticker (in
`ticker_yfinance_pr`) and a US-listed *ETF* (in `ticker_yfinance_tr`). Because a
library row has ONE `base_currency`, the two emitted output tickers could not be
priced in their true currencies at once. The prior currency fix set the row to
USD (correct for the ETF, wrong for the index).

Fix: split each into TWO rows so every ticker gets its correct currency:
  - an INDEX row   — `yfinance PR`, PR ticker only, native currency (EUR / CNY)
  - an ETF row     — `yfinance TR`, TR ticker only, USD

Edits ONLY the FEZ and ASHR rows; every other line stays byte-for-byte. Backup
written first.
"""
import csv
import io
import os
import shutil

LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "index_library.csv"))
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")

# Per ETF ticker: the native currency of its paired index, and the ETF's real name.
SPLIT = {
    "FEZ":  {"index_ccy": "EUR", "etf_name": "SPDR EURO STOXX 50 ETF"},
    "ASHR": {"index_ccy": "CNY", "etf_name": "Xtrackers Harvest CSI 300 China A-Shares ETF"},
}


def parse(line):
    return next(csv.reader(io.StringIO(line)))


def emit(fields):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(fields)
    return buf.getvalue()


def main():
    with open(LIB, "r", encoding="utf-8", newline="") as f:
        raw = f.readlines()

    header = parse(raw[0])
    ix = {n: i for i, n in enumerate(header)}
    TR, PR, NAME, CCY, SRC, UNITS, SDASH, PROXY = (
        ix["ticker_yfinance_tr"], ix["ticker_yfinance_pr"], ix["name"],
        ix["base_currency"], ix["data_source"], ix["units"],
        ix["simple_dash"], ix["proxy_flag"],
    )

    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup = os.path.join(BACKUP_DIR, "index_library.csv.pre_split")
    shutil.copy2(LIB, backup)

    out = [raw[0]]
    changed = []
    for line in raw[1:]:
        stripped = line.rstrip("\r\n")
        if not stripped:
            out.append(line)
            continue
        f = parse(stripped)
        tr = f[TR].strip() if len(f) > TR else ""
        if tr not in SPLIT:
            out.append(line)                      # untouched, verbatim
            continue
        cfg = SPLIT[tr]
        nl = "\n" if line.endswith("\n") else ""

        # INDEX row: PR ticker only, native currency, comp-only (simple shows the ETF)
        idx = list(f)
        idx[TR] = ""
        idx[CCY] = cfg["index_ccy"]
        idx[SRC] = "yfinance PR"
        idx[UNITS] = "Index"
        idx[SDASH] = "False"

        # ETF row: TR ticker only, USD, keeps the row's simple_dash membership
        etf = list(f)
        etf[PR] = ""
        etf[NAME] = cfg["etf_name"]
        etf[CCY] = "USD"
        etf[SRC] = "yfinance TR"
        etf[UNITS] = "Price"
        etf[PROXY] = "False"
        # simple_dash stays whatever the original row had (the ETF is what simple shows)

        out.append(emit(idx) + nl)
        out.append(emit(etf) + nl)
        changed.append((tr, f[NAME], cfg["index_ccy"]))

    with open(LIB, "w", encoding="utf-8", newline="") as f:
        f.writelines(out)

    print(f"Backup: {backup}")
    for tr, name, ccy in changed:
        print(f"  split {tr}: '{name}' -> INDEX row ({ccy}) + ETF row (USD)")
    print(f"Rows: {len(raw)-1} -> {len(out)-1} (+{len(out)-len(raw)})")


if __name__ == "__main__":
    main()
