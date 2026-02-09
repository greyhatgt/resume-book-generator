#!/usr/bin/env python3
"""CLI: Generate resume book from CSV and PDFs."""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.merge.pdf_merger import (
    add_internal_links,
    get_pdf_page_count,
    merge_pdfs_with_sections,
    set_pdf_outline,
)
from src.typst.generator import (
    compute_page_offsets,
    compute_section_page_numbers,
    generate_section_pages_typst,
    generate_typst,
    load_candidates,
)


def estimate_toc_pages(num_candidates: int) -> int:
    """Estimate TOC pages (~20 candidates per page, min 1)."""
    return max(1, math.ceil(num_candidates / 20))


def run_typst_compile(typ_path: Path, output_pdf: Path) -> bool:
    """Run typst compile. Returns True on success."""
    typst = shutil.which("typst")
    if not typst:
        print("Error: typst not found. Install it: https://typst.app", file=sys.stderr)
        return False
    result = subprocess.run(
        [typst, "compile", str(typ_path), str(output_pdf)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("typst compile failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate resume book from CSV and PDFs")
    parser.add_argument("--csv", required=True, type=Path, help="Path to candidates.csv")
    parser.add_argument("--input", required=True, type=Path, help="Folder containing resume PDFs")
    parser.add_argument("--output", required=True, type=Path, help="Output PDF path")
    parser.add_argument("--title", default="Resume Book", help="Cover page title")
    parser.add_argument("--subtitle", default=None, help="Cover page subtitle")
    args = parser.parse_args()

    csv_path = args.csv
    input_dir = args.input
    output_path = args.output

    if not csv_path.exists():
        print(f"Error: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    if not input_dir.is_dir():
        print(f"Error: Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    # Load candidates
    try:
        candidates = load_candidates(csv_path, input_dir)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if candidates.empty:
        print("Error: No valid candidates in CSV", file=sys.stderr)
        return 1

    # Warn about missing PDFs
    missing = []
    for _, row in candidates.iterrows():
        fn = str(row["filename"]).strip()
        if not (input_dir / fn).exists():
            missing.append(fn)
    if missing:
        print(f"Warning: Missing PDFs: {missing}", file=sys.stderr)

    # Output dir for intermediate files
    out_dir = output_path.parent
    project_root = Path(__file__).resolve().parent.parent
    typ_path = out_dir / "cover_toc.typ"
    cover_toc_path = out_dir / "cover_toc.pdf"

    # Copy logo to output dir so typst can resolve it
    logo_src = project_root / "assets" / "grey_hat_hat_small_400x400.png"
    if logo_src.exists():
        shutil.copy2(logo_src, out_dir / "grey_hat_hat_small_400x400.png")

    # Generate cover + TOC (first pass, no section links yet)
    toc_estimate = estimate_toc_pages(len(candidates))
    generate_typst(candidates, typ_path, args.title, args.subtitle)

    if not run_typst_compile(typ_path, cover_toc_path):
        return 1

    actual_toc_pages = get_pdf_page_count(cover_toc_path)
    actual_toc_only = actual_toc_pages - 1

    if actual_toc_only != toc_estimate:
        generate_typst(candidates, typ_path, args.title, args.subtitle)
        if not run_typst_compile(typ_path, cover_toc_path):
            return 1

    # Generate section title pages (one per grad_date group)
    groups = list(candidates.groupby("grad_date", sort=False))
    grad_dates = [str(gd) for gd, _ in groups]
    section_typ_path = out_dir / "section_pages.typ"
    section_pdf_path = out_dir / "section_pages.pdf"
    generate_section_pages_typst(grad_dates, section_typ_path)
    if not run_typst_compile(section_typ_path, section_pdf_path):
        return 1

    # Compute section page numbers for link injection (section headings -> section pages)
    section_page_numbers = compute_section_page_numbers(
        candidates, input_dir, actual_toc_pages
    )
    section_links = [(label, page) for label, page in section_page_numbers.items()]

    # Build resume paths by group
    resume_paths_by_group: list[list[Path]] = []
    for _, group_df in groups:
        paths: list[Path] = []
        for _, row in group_df.iterrows():
            fn = str(row["filename"]).strip()
            p = input_dir / fn
            if p.exists():
                paths.append(p)
        resume_paths_by_group.append(paths)

    merge_pdfs_with_sections(
        cover_toc_path, section_pdf_path, resume_paths_by_group, output_path
    )

    # Add internal links (name -> resume page) via PyMuPDF post-processing
    page_offsets = compute_page_offsets(candidates, input_dir, actual_toc_pages)
    link_candidates = [
        (str(row["name"]).strip(), page_offsets.get(str(row["filename"]).strip(), 1))
        for _, row in candidates.iterrows()
    ]
    add_internal_links(
        output_path, link_candidates, actual_toc_pages, section_links=section_links
    )

    # Add PDF outline for native TOC in viewers
    outline_sections: list[tuple[str, int, list[tuple[str, int]]]] = []
    section_page_0 = actual_toc_pages  # first section page (0-based)
    for grad_date, group_df in groups:
        label = str(grad_date).strip()
        name_pages: list[tuple[str, int]] = []
        for _, row in group_df.iterrows():
            fn = str(row["filename"]).strip()
            page_1 = page_offsets.get(fn, 1)
            name_pages.append((str(row["name"]).strip(), page_1 - 1))
        outline_sections.append((label, section_page_0, name_pages))
        section_page_0 += 1  # section title page
        for _, row in group_df.iterrows():
            fn = str(row["filename"]).strip()
            path = input_dir / fn
            section_page_0 += get_pdf_page_count(path) if path.exists() else 1

    set_pdf_outline(output_path, outline_sections, actual_toc_pages)

    print(f"Generated: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
