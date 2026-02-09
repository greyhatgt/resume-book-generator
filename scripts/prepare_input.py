#!/usr/bin/env python3
"""Prepare input folder: copy PDFs from input-raw (minus duplicates) and convert DOCX to PDF.

Creates input/ with all PDFs ready for the resume book. Requires LibreOffice for DOCX conversion.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Import from same package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.convert_docx_to_pdf import _find_libreoffice, convert_docx_to_pdf


def _is_duplicate(filename: str) -> bool:
    """True if file is a duplicate (e.g. ends with (1) before extension)."""
    stem = Path(filename).stem
    return bool(re.search(r"\(\d+\)\s*$", stem))


def prepare_input(
    raw_dir: Path,
    output_dir: Path,
    converted_dir: Path | None = None,
) -> None:
    """Copy PDFs from raw_dir to output_dir (skipping duplicates), convert DOCX to PDF."""
    output_dir.mkdir(parents=True, exist_ok=True)
    conv_dir = converted_dir if converted_dir is not None else output_dir

    # Copy PDFs, skip (1) duplicates
    pdf_count = 0
    for f in raw_dir.iterdir():
        if f.suffix.lower() != ".pdf":
            continue
        if _is_duplicate(f.name):
            print(f"Skipping duplicate: {f.name}")
            continue
        dest = output_dir / f.name
        shutil.copy2(f, dest)
        pdf_count += 1

    print(f"Copied {pdf_count} PDF(s) from {raw_dir} to {output_dir}")

    # Convert DOCX to PDF
    docx_files = list(raw_dir.glob("*.docx")) + list(raw_dir.glob("*.DOCX"))
    if docx_files:
        libreoffice = _find_libreoffice()
        if not libreoffice:
            print(
                "Warning: LibreOffice not found. DOCX files not converted. "
                "Install LibreOffice or run: nix-shell --run 'uv run python scripts/convert_docx_to_pdf.py'",
                file=sys.stderr,
            )
        else:
            n = convert_docx_to_pdf(raw_dir, conv_dir)
            if n > 0 and conv_dir != output_dir:
                for pdf in conv_dir.glob("*.pdf"):
                    shutil.copy2(pdf, output_dir / pdf.name)
                    print(f"Copied converted: {pdf.name}")
            elif n > 0:
                print(f"Converted {n} DOCX to PDF in {output_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare input folder from input-raw")
    parser.add_argument("--raw", type=Path, default=Path("input-raw"), help="Raw resumes folder")
    parser.add_argument("--output", type=Path, default=Path("input"), help="Output folder for PDFs")
    parser.add_argument(
        "--converted-dir",
        type=Path,
        default=None,
        help="Temp folder for DOCX conversion (default: same as output)",
    )
    args = parser.parse_args()

    if not args.raw.is_dir():
        print(f"Error: Raw directory not found: {args.raw}", file=sys.stderr)
        return 1

    prepare_input(args.raw, args.output, args.converted_dir)
    print(f"Ready: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
