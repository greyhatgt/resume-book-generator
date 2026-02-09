#!/usr/bin/env python3
"""Sync a Google Sheet to candidates.csv.

For public sheets (Anyone with the link): no credentials needed.
For private sheets: set up a service account and share the sheet with its
client_email. Place credentials at ~/.config/gspread/service_account.json
or pass --credentials.

Usage:
  uv run python scripts/sync_sheet_to_csv.py SHEET_URL
  uv run python scripts/sync_sheet_to_csv.py --sheet-id ID --output candidates.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import ssl
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Expected CSV columns (matches candidates.csv schema)
CSV_COLUMNS = [
    "filename",
    "name",
    "major",
    "grad_date",
    "email",
    "linkedin",
    "github",
    "phone",
    "tags",
]


def _extract_sheet_id(url_or_id: str) -> str | None:
    """Extract spreadsheet ID from URL or return as-is if it looks like an ID."""
    # Already a raw ID (alphanumeric, 44 chars typical for Sheets IDs)
    if re.match(r"^[a-zA-Z0-9_-]{40,}$", url_or_id):
        return url_or_id
    # URL: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/...
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_or_id)
    if m:
        return m.group(1)
    return None


def _create_ssl_context() -> ssl.SSLContext:
    """Create SSL context using certifi bundle if available."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _fetch_public_csv(sheet_id: str, gid: str = "0") -> str:
    """Download sheet as CSV via public export URL."""
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid}"
    )
    req = Request(url, headers={"User-Agent": "resume-book-generator/1.0"})
    ctx = _create_ssl_context()
    with urlopen(req, timeout=30, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_private_csv(sheet_id: str, credentials_path: Path | None) -> str:
    """Fetch sheet via gspread service account, return CSV string."""
    try:
        import gspread
    except ImportError:
        raise RuntimeError(
            "gspread not installed. Run: uv sync --extra sync"
        ) from None

    if credentials_path and credentials_path.exists():
        gc = gspread.service_account(filename=str(credentials_path))
    else:
        gc = gspread.service_account()

    sh = gc.open_by_key(sheet_id)
    worksheet = sh.sheet1
    rows = worksheet.get_all_values()

    if not rows:
        return "filename,name,major,grad_date,email,linkedin,github,phone,tags\n"

    # Determine header row (first row)
    header = [str(cell).strip() for cell in rows[0]]
    # Normalize header to match expected columns (case-insensitive)
    header_lower = {h.lower(): h for h in header}

    # Build output with standard column order; fill missing columns
    output_rows: list[list[str]] = []
    for row in rows[1:]:  # skip header
        row_dict = dict(zip(header, (str(c).strip() for c in row)))
        output_row = []
        for col in CSV_COLUMNS:
            key = header_lower.get(col.lower(), col)
            output_row.append(row_dict.get(key, row_dict.get(col, "")))
        output_rows.append(output_row)

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    writer.writerows(output_rows)
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync a Google Sheet to candidates.csv"
    )
    parser.add_argument(
        "url_or_id",
        nargs="?",
        help="Google Sheet URL or spreadsheet ID",
    )
    parser.add_argument(
        "--sheet-id",
        help="Spreadsheet ID (alternative to positional arg)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("candidates.csv"),
        help="Output CSV path (default: candidates.csv)",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=None,
        help="Service account JSON path (default: ~/.config/gspread/service_account.json)",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Force public export (no auth). Fails if sheet is private.",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Force gspread/service account auth. Share sheet with service account email.",
    )
    parser.add_argument(
        "--gid",
        default="0",
        help="Sheet GID for public export (default: 0 = first sheet)",
    )
    args = parser.parse_args()

    sheet_id = args.sheet_id or args.url_or_id
    if not sheet_id:
        parser.error("Provide sheet URL or ID, or use --sheet-id")
        return 1

    extracted = _extract_sheet_id(sheet_id)
    if not extracted:
        print(
            "Error: Could not extract spreadsheet ID. Use a URL like "
            "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/...",
            file=sys.stderr,
        )
        return 1

    try:
        if args.private:
            csv_content = _fetch_private_csv(
                extracted,
                args.credentials,
            )
        elif args.public:
            csv_content = _fetch_public_csv(extracted, args.gid)
        else:
            # Try public first; fall back to private on 403
            try:
                csv_content = _fetch_public_csv(extracted, args.gid)
            except HTTPError as e:
                if e.code == 403:
                    print(
                        "Sheet not publicly accessible. Trying service account...",
                        file=sys.stderr,
                    )
                    csv_content = _fetch_private_csv(
                        extracted,
                        args.credentials,
                    )
                else:
                    raise
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (HTTPError, URLError) as e:
        print(f"Error fetching sheet: {e}", file=sys.stderr)
        return 1

    args.output.write_text(csv_content, encoding="utf-8")
    print(f"Synced to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
