"""
sources/base.py
===============
Shared plumbing for source modules and the root-level fetch_macro_*
coordinators.  Everything that was duplicated across fetch_macro_international,
fetch_macro_dbnomics, fetch_macro_ifo, fetch_macro_us_fred, and fetch_hist
lives here.

Provides:
  - last_friday_on_or_before / build_friday_spine — Friday weekly-spine helpers
  - fetch_with_backoff — HTTP GET with exponential backoff on 429/5xx
  - get_sheets_service — Google Sheets v4 client (returns None if creds empty)
  - push_df_to_sheets — unified DataFrame → Sheets writer:
      * tab auto-create, SHEETS_PROTECTED_TABS guard
      * batched writes (10k rows/batch)
      * optional prefix_rows for metadata header
      * NaN/None/numeric normalization via sv()
  - sv — Sheets value sanitizer
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from library_utils import SHEETS_PROTECTED_TABS


# ---------------------------------------------------------------------------
# FRIDAY-SPINE HELPERS
# ---------------------------------------------------------------------------

def last_friday_on_or_before(d: date) -> date:
    """Most recent Friday on or before d (returns d itself if d is Friday)."""
    return d - timedelta(days=(d.weekday() - 4) % 7)


def build_friday_spine(start: str, end: date) -> pd.DatetimeIndex:
    """DatetimeIndex of every Friday from start (YYYY-MM-DD) to end (inclusive)."""
    first = last_friday_on_or_before(datetime.strptime(start, "%Y-%m-%d").date())
    return pd.date_range(start=first, end=end, freq="W-FRI")


# ---------------------------------------------------------------------------
# HTTP FETCH
# ---------------------------------------------------------------------------

def fetch_with_backoff(
    url: str,
    params: dict | None = None,
    label: str = "",
    accept_csv: bool = False,
    retries: int = 5,
    backoff_base: int = 2,
    timeout: int = 30,
) -> dict | str | None:
    """
    Generic HTTP GET with exponential backoff on 429 / 5xx.

    Returns parsed JSON (or raw text when accept_csv=True), or None on failure.
    """
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)

            if resp.status_code == 200:
                return resp.text if accept_csv else resp.json()

            if resp.status_code in (429, 503) or resp.status_code >= 500:
                wait = backoff_base ** (attempt + 1)
                print(
                    f"  [{label}] HTTP {resp.status_code}. "
                    f"Backing off {wait}s (attempt {attempt + 1}/{retries})"
                )
                time.sleep(wait)
                continue

            print(f"  [{label}] HTTP {resp.status_code} — skipping")
            return None

        except requests.exceptions.Timeout:
            wait = backoff_base ** (attempt + 1)
            print(f"  [{label}] Timeout. Backing off {wait}s")
            time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"  [{label}] Request error: {e} — skipping")
            return None

    print(f"  [{label}] All {retries} attempts failed — skipping")
    return None


# ---------------------------------------------------------------------------
# GOOGLE SHEETS
# ---------------------------------------------------------------------------

_SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_sheets_service(credentials_json: str):
    """
    Build a Sheets v4 service client from a JSON credentials string.
    Returns None if the credentials string is empty/None so callers can
    short-circuit cleanly in local dev.
    """
    if not credentials_json:
        return None
    creds_dict = json.loads(credentials_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=_SHEETS_SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def sv(v):
    """Sanitize a single value for Sheets: NaN/None → '', numeric → float, else str."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    return str(v)


def push_df_to_sheets(
    service,
    spreadsheet_id: str,
    tab_name: str,
    df: pd.DataFrame,
    label: str = "",
    prefix_rows: list | None = None,
    value_input_option: str = "USER_ENTERED",
    batch_size: int = 10_000,
) -> None:
    """
    Write a DataFrame to a Google Sheets tab.  Creates the tab if missing,
    clears existing content, and writes in batches to stay under the Sheets
    API payload limit.  Respects SHEETS_PROTECTED_TABS.

    Args:
        service: Sheets v4 service from get_sheets_service(); no-op if None.
        spreadsheet_id: target spreadsheet ID.
        tab_name: destination tab.
        df: DataFrame to write (header row is auto-prepended).
        label: log prefix, e.g. "Phase C".
        prefix_rows: rows to write above the header (e.g. metadata rows).
        value_input_option: "USER_ENTERED" or "RAW".
        batch_size: max rows per update call.
    """
    if service is None:
        print(f"  [{label}] GOOGLE_CREDENTIALS not set — skipping Sheets push")
        return
    if df.empty:
        print(f"  [{label}] Empty DataFrame — skipping Sheets push")
        return
    if tab_name in SHEETS_PROTECTED_TABS:
        print(f"  [{label}] REFUSED: '{tab_name}' is a protected tab")
        return

    sheets = service.spreadsheets()

    # Ensure tab exists
    meta = sheets.get(spreadsheetId=spreadsheet_id).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if tab_name not in existing:
        print(f"  [{label}] Creating tab '{tab_name}'...")
        sheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
        ).execute()

    # Clear existing content
    sheets.values().clear(
        spreadsheetId=spreadsheet_id, range=f"{tab_name}!A:ZZZ"
    ).execute()

    header = list(df.columns)
    data_rows = [[sv(v) for v in row] for row in df.itertuples(index=False)]
    values = (prefix_rows if prefix_rows else []) + [header] + data_rows

    for start in range(0, len(values), batch_size):
        chunk = values[start:start + batch_size]
        row_start = start + 1  # 1-indexed for A1 notation
        sheets.values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{tab_name}!A{row_start}",
            valueInputOption=value_input_option,
            body={"values": chunk},
        ).execute()

    print(f"  [{label}] Written {len(values)} rows to '{tab_name}'")


def ensure_tab(service, spreadsheet_id: str, tab_name: str, label: str = "") -> None:
    """
    Ensure a Sheets tab exists, creating it if necessary.  No-op if service is
    None.  Exposed separately from push_df_to_sheets for callers that need to
    manage tab existence outside of a DataFrame write (e.g. legacy cleanup).
    """
    if service is None:
        return
    sheets = service.spreadsheets()
    meta = sheets.get(spreadsheetId=spreadsheet_id).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if tab_name not in existing:
        print(f"  [{label}] Creating tab '{tab_name}'...")
        sheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
        ).execute()
