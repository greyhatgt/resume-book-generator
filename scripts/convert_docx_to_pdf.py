#!/usr/bin/env python3
"""Convert DOCX files to PDF using LibreOffice.

Requires LibreOffice installed (e.g. apt install libreoffice, or nix-shell with libreoffice).
Outputs PDFs to a folder you specify (default: input-pdf).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _find_libreoffice() -> str | None:
    """Find libreoffice or soffice executable."""
    for cmd in ("libreoffice", "soffice"):
        path = shutil.which(cmd)
        if path:
            return path
    return None


def convert_docx_to_pdf(input_dir: Path, output_dir: Path) -> int:
    """Convert all DOCX files in input_dir to PDF in output_dir. Returns count converted."""
    libreoffice = _find_libreoffice()
    if not libreoffice:
        print(
            "Error: LibreOffice not found. Install it (e.g. apt install libreoffice) "
            "or add to nix shell.",
            file=sys.stderr,
        )
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    docx_files = [f for f in input_dir.iterdir() if f.suffix.lower() == ".docx"]
    if not docx_files:
        print(f"No DOCX files in {input_dir}")
        return 0

    converted = 0
    for docx_path in sorted(docx_files):
        try:
            result = subprocess.run(
                [
                    libreoffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(output_dir),
                    str(docx_path.resolve()),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                pdf_name = docx_path.with_suffix(".pdf").name
                print(f"Converted: {docx_path.name} -> {output_dir / pdf_name}")
                converted += 1
            else:
                print(f"Failed {docx_path.name}: {result.stderr}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"Timeout converting {docx_path.name}", file=sys.stderr)
        except Exception as e:
            print(f"Error converting {docx_path.name}: {e}", file=sys.stderr)

    return converted


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert DOCX files to PDF via LibreOffice")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("input-raw"),
        help="Folder containing DOCX files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("input-pdf"),
        help="Output folder for converted PDFs",
    )
    args = parser.parse_args()

    if not args.input.is_dir():
        print(f"Error: Input directory not found: {args.input}", file=sys.stderr)
        return 1

    n = convert_docx_to_pdf(args.input, args.output)
    print(f"Converted {n} file(s) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
