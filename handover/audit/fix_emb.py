"""
Remediation: EMB proxy + currency fix
=====================================
Audit finding 9a/9b (FACTIQ_AUDIT_PLAN.md audit, 2026-07-12):

  The single US-listed USD fund EMB (iShares J.P. Morgan USD Emerging Markets
  Bond ETF) was used in index_library.csv as the proxy for 9 rows: 8 country
  "USD-Hedged" government-bond indices (Brazil/Korea/Mexico/Indonesia/Saudi/
  South Africa/Turkey/Argentina) + the real USD EM Debt fund. Because the
  pipeline deduplicates on ticker, all 9 collapsed to one output row, which
  inherited a country currency (ARS) and produced a corrupted USD 1Y return
  (+11.69% local -> -13.35% USD via a phantom ARS->USD conversion).

Fix (per Kas, 2026-07-12): remove the 8 country-proxy rows; keep EMB as a single
standalone USD ETF with corrected labels.

This script edits ONLY the 9 EMB rows and leaves every other line byte-for-byte
unchanged. A timestamped backup is written first.
"""
import csv
import io
import os
import shutil

LIB = os.path.join(os.path.dirname(__file__), "..", "data", "index_library.csv")
LIB = os.path.abspath(LIB)
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")

HEADER_TR_IDX = None  # resolved from header
COLS = None


def parse(line):
    return next(csv.reader(io.StringIO(line)))


def emit(fields):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(fields)
    return buf.getvalue()


def main():
    with open(LIB, "r", encoding="utf-8", newline="") as f:
        raw_lines = f.readlines()

    header = parse(raw_lines[0])
    ix = {name: i for i, name in enumerate(header)}
    tr = ix["ticker_yfinance_tr"]
    ccy = ix["base_currency"]
    name_i = ix["name"]
    pflag = ix["proxy_flag"]
    ptype = ix["proxy_type"]
    hedged = ix["hedged"]

    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup = os.path.join(BACKUP_DIR, "index_library.csv.pre_emb")
    shutil.copy2(LIB, backup)

    out = [raw_lines[0]]
    removed, edited = [], []

    for line in raw_lines[1:]:
        stripped = line.rstrip("\r\n")
        if not stripped:
            out.append(line)
            continue
        fields = parse(stripped)
        is_emb = len(fields) > tr and fields[tr].strip() == "EMB"
        if not is_emb:
            out.append(line)          # untouched, verbatim
            continue

        if fields[ccy].strip().upper() != "USD":
            removed.append(fields[name_i])   # drop the 8 country proxies
            continue

        # The real USD EM Debt fund -> keep as standalone ETF, fix labels
        fields[name_i] = "iShares J.P. Morgan USD Emerging Markets Bond ETF"
        fields[ccy] = "USD"
        fields[hedged] = "False"
        fields[pflag] = "False"
        fields[ptype] = ""
        newline = "\n" if line.endswith("\n") else ""
        out.append(emit(fields) + newline)
        edited.append(fields[name_i])

    with open(LIB, "w", encoding="utf-8", newline="") as f:
        f.writelines(out)

    print(f"Backup written: {backup}")
    print(f"Removed {len(removed)} country-proxy rows:")
    for r in removed:
        print(f"  - {r}")
    print(f"Kept/relabeled {len(edited)} standalone EMB row(s):")
    for e in edited:
        print(f"  * {e}")


if __name__ == "__main__":
    main()
