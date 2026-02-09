#!/usr/bin/env python3
"""Generate a template candidates.csv from resume files in input/.

Scans the input folder for PDFs and infers names from filenames.
Output CSV has placeholder data—fill in major, grad_date, email, linkedin, github
manually or via the ChatGPT prompt in the plan appendix.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def _infer_name_from_filename(filename: str) -> str:
    """Infer candidate name from filename. Returns best guess."""
    base = Path(filename).stem

    def _looks_like_name(s: str) -> bool:
        if not s or len(s) < 2:
            return False
        # Reject if too many odd chars or ends with file extension-like stuff
        if s.lower().endswith(("resume", "cv", "gt", ".r", ".pdf")):
            return False
        # Reject suffix like (1) or _0825
        if re.search(r"\(\d+\)$|_\d{4}$", s):
            return False
        # Prefer parts with spaces (First Last) or Title Case
        words = s.split()
        return len(words) >= 1 and all(w[0].isupper() or w.isupper() for w in words if w)

    # Try "X - Name" or "X - Name1 - Name2" (split only on " - "; prefer last segment)
    segments = [s.strip() for s in base.split(" - ")]
    for candidate in reversed(segments):
        if _looks_like_name(candidate):
            # Strip trailing (1), (2), etc.
            return re.sub(r"\s*\(\d+\)\s*$", "", candidate).strip()

    # Fallback: "FirstName_LastName_Resume" -> FirstName LastName
    parts = re.split(r"[\s_]+", base)
    skip = {"resume", "cv", "gt", "georgia", "tech", "greyhat", "grey", "hat", "application"}
    clean = [
        p for p in parts
        if p.lower() not in skip and not p.isdigit()
        and "." not in p  # skip Scrappe.r etc.
        and "(" not in p  # skip Bansal(1) etc.
    ]
    if len(clean) >= 2:
        return " ".join(clean[: min(4, len(clean))])
    if clean:
        return " ".join(clean)
    return base.replace("_", " ").replace("-", " ").strip() or "Unknown"


def generate_csv(input_dir: Path, output_path: Path) -> None:
    """Generate template CSV from PDF files in input_dir."""
    pdfs = sorted(f for f in input_dir.iterdir() if f.suffix.lower() == ".pdf")
    rows: list[dict[str, str]] = []
    for p in pdfs:
        name = _infer_name_from_filename(p.name)
        rows.append({
            "filename": p.name,
            "name": name,
            "major": "",
            "grad_date": "Unknown",
            "email": "",
            "linkedin": "",
            "github": "",
            "phone": "",
            "tags": "",
        })
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["filename", "name", "major", "grad_date", "email", "linkedin", "github", "phone", "tags"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {output_path} with {len(rows)} candidates (PDFs only)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate template candidates.csv from resume PDFs")
    parser.add_argument("--input", type=Path, default=Path("input"), help="Folder with resume PDFs")
    parser.add_argument("--output", type=Path, default=Path("candidates.csv"), help="Output CSV path")
    args = parser.parse_args()
    if not args.input.is_dir():
        print(f"Error: Input directory not found: {args.input}", file=__import__("sys").stderr)
        return 1
    generate_csv(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
