#!/usr/bin/env python3
"""Sync a Google Drive folder to the input PDFs folder.

Requires the folder to be shared with "Anyone with the link" (viewer access).
For private folders, use Google Drive desktop sync or rclone instead.

Usage:
  uv run python scripts/sync_drive_to_input.py FOLDER_URL
  uv run python scripts/sync_drive_to_input.py --folder-id FOLDER_ID --output input
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _extract_folder_id(url_or_id: str) -> str | None:
    """Extract folder ID from URL or return as-is if it looks like an ID."""
    # Already a raw ID (alphanumeric, 33-44 chars typical for Drive IDs)
    if re.match(r"^[a-zA-Z0-9_-]{33,}$", url_or_id):
        return url_or_id
    # URL: https://drive.google.com/drive/folders/FOLDER_ID
    m = re.search(r"/folders/([a-zA-Z0-9_-]+)", url_or_id)
    if m:
        return m.group(1)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync a Google Drive folder to the input PDFs folder"
    )
    parser.add_argument(
        "url_or_id",
        nargs="?",
        help="Google Drive folder URL or folder ID (e.g. https://drive.google.com/drive/folders/...)",
    )
    parser.add_argument(
        "--folder-id",
        help="Google Drive folder ID (alternative to positional arg)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("input"),
        help="Output directory for downloaded PDFs (default: input)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress gdown output",
    )
    args = parser.parse_args()

    folder_id = args.folder_id or args.url_or_id
    if not folder_id:
        parser.error("Provide folder URL or ID, or use --folder-id")
        return 1

    extracted = _extract_folder_id(folder_id)
    if not extracted:
        print(
            "Error: Could not extract folder ID. Use a URL like "
            "https://drive.google.com/drive/folders/FOLDER_ID",
            file=sys.stderr,
        )
        return 1

    try:
        import gdown
    except ImportError:
        print(
            "Error: gdown not installed. Run: uv sync --extra sync",
            file=sys.stderr,
        )
        return 1

    url = f"https://drive.google.com/drive/folders/{extracted}"
    output_path = args.output.resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Downloading from {url} to {output_path}...")
    gdown.download_folder(
        url,
        output=str(output_path),
        quiet=args.quiet,
        use_cookies=False,
        remaining_ok=True,
    )
    print(f"Synced to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
