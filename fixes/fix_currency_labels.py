"""
Remediation: US-listed USD ETF currency mislabels (FEZ / ASHR / HYXU)
=====================================================================
Audit finding (2026-07-13): three US-listed, USD-denominated ETFs carry a
foreign `base_currency` in data/index_library.csv. Because the market pipeline
derives its FX adjustment purely from `base_currency`
(fetch_data.py: `local_ccy = None if ccy == "USD" else ccy`), each of these
rows gets a spurious foreign->USD conversion applied to its already-USD return
columns — the same bug class as the already-fixed EMB=ARS case.

  FEZ  (SPDR EURO STOXX 50 ETF)                 labelled EUR -> is USD
  ASHR (Xtrackers Harvest CSI 300 China A ETF)  labelled CNY -> is USD
  HYXU (iShares Interest Rate Hedged / Currency
        Hedged Intl High Yield Bond ETF)        labelled EUR -> is USD

All three trade on US exchanges and their yfinance price series are already in
USD (their tickers carry NO foreign-exchange suffix, unlike London `.L`,
Frankfurt `.DE`, Tokyo `.T`, etc.). They therefore need base_currency=USD and
no hedge-to-USD.

Fix (mirrors audit/fix_emb.py): edit ONLY these 3 rows, leave every other line
byte-for-byte unchanged, write a timestamped backup first.
  - base_currency -> USD (all three)
  - HYXU only: hedged True -> False, hedge_currency USD -> "" (a USD instrument
    needs no hedge-to-USD; keeps the FX-relevant fields internally consistent,
    matching how fix_emb.py left the standalone USD EMB row).

This script ALSO prints (report-only, changes nothing) any OTHER confirmed
yfinance row whose fetched ticker looks US-listed (no exchange suffix) yet
carries a non-USD base_currency, so Kas can decide on those separately.
"""
import csv
import io
import os
import shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "data", "index_library.csv"))
BACKUP_DIR = os.path.join(HERE, "backups")

# ticker_yfinance_tr values of the three rows to relabel.
TARGETS = {"FEZ", "ASHR", "HYXU"}


def parse(line):
    return next(csv.reader(io.StringIO(line)))


def emit(fields):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(fields)
    return buf.getvalue()


def _looks_us_listed(ticker: str) -> bool:
    """True for a plain US-listed equity/ETF ticker (no exchange suffix).

    Excludes index/FX/futures/crypto pseudo-tickers (^GSPC, EURUSD=X, CL=F,
    BTC-USD) and any dotted foreign-exchange suffix (.L/.DE/.T/.TO/.AX/...).
    """
    t = ticker.strip()
    if not t:
        return False
    if t.startswith("^") or "=" in t or "-" in t or "." in t:
        return False
    return True


def main():
    with open(LIB, "r", encoding="utf-8", newline="") as f:
        raw_lines = f.readlines()

    header = parse(raw_lines[0])
    ix = {name: i for i, name in enumerate(header)}
    tr_i     = ix["ticker_yfinance_tr"]
    pr_i     = ix["ticker_yfinance_pr"]
    ccy_i    = ix["base_currency"]
    hedged_i = ix["hedged"]
    hedgec_i = ix["hedge_currency"]
    name_i   = ix["name"]
    ds_i     = ix["data_source"]
    vs_i     = ix["validation_status"]

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(BACKUP_DIR, f"index_library.csv.pre_currency_{stamp}")
    shutil.copy2(LIB, backup)

    out = [raw_lines[0]]
    before, after = {}, {}
    scan_hits = []

    for line in raw_lines[1:]:
        stripped = line.rstrip("\r\n")
        if not stripped:
            out.append(line)
            continue
        fields = parse(stripped)
        if len(fields) <= tr_i:
            out.append(line)
            continue

        tr = fields[tr_i].strip()

        # --- report-only scan (all confirmed yfinance rows) ---
        ds = fields[ds_i].strip() if len(fields) > ds_i else ""
        vs = fields[vs_i].strip() if len(fields) > vs_i else ""
        ccy_raw = fields[ccy_i].strip().upper() if len(fields) > ccy_i else ""
        if ds in ("yfinance PR", "yfinance TR") and vs == "CONFIRMED" \
                and ccy_raw not in ("USD", "USX", "", "N/A", "NAN"):
            for tk in (fields[tr_i].strip(), fields[pr_i].strip()):
                if _looks_us_listed(tk):
                    scan_hits.append((fields[name_i], tk, ccy_raw, ds))

        # --- targeted edit (the 3 named rows) ---
        if tr not in TARGETS:
            out.append(line)            # untouched, verbatim
            continue

        before[tr] = (fields[ccy_i], fields[hedged_i], fields[hedgec_i])
        fields[ccy_i] = "USD"
        if tr == "HYXU":
            fields[hedged_i] = "False"
            fields[hedgec_i] = ""
        after[tr] = (fields[ccy_i], fields[hedged_i], fields[hedgec_i])

        newline = "\n" if line.endswith("\n") else ""
        out.append(emit(fields) + newline)

    with open(LIB, "w", encoding="utf-8", newline="") as f:
        f.writelines(out)

    print(f"Backup written: {backup}")
    print(f"\nEdited {len(after)} row(s) (base_currency / hedged / hedge_currency):")
    for tr in ("FEZ", "ASHR", "HYXU"):
        if tr in before:
            b, a = before[tr], after[tr]
            print(f"  {tr}:")
            print(f"    BEFORE  base_currency={b[0]!r}  hedged={b[1]!r}  hedge_currency={b[2]!r}")
            print(f"    AFTER   base_currency={a[0]!r}  hedged={a[1]!r}  hedge_currency={a[2]!r}")
        else:
            print(f"  {tr}: NOT FOUND (no ticker_yfinance_tr == {tr!r})")

    print("\n[report-only] Other confirmed-yfinance rows whose ticker looks "
          "US-listed but base_currency is non-USD:")
    others = [h for h in scan_hits if h[1] not in TARGETS]
    if not others:
        print("  (none beyond the 3 fixed above)")
    else:
        for name, tk, ccy, ds in others:
            print(f"  {tk:12} {ccy:4} [{ds}]  {name}")


if __name__ == "__main__":
    main()
