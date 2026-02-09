#!/usr/bin/env python3
"""CLI: Generate resume book from CSV and PDFs."""

from __future__ import annotations

import argparse
import json
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
    DEFAULT_TAG_SECTIONS,
    compute_page_offsets,
    compute_section_page_numbers,
    generate_section_pages_typst,
    generate_typst,
    load_candidates,
)

CONFIG_FILENAME = "resume_book.json"


def load_config(project_root: Path) -> tuple[list[str], list[str]]:
    """Load tag_sections and hidden_tags from config file. Returns (tag_sections, hidden_tags)."""
    tag_sections = DEFAULT_TAG_SECTIONS
    hidden_tags: list[str] = []
    config_path = project_root / CONFIG_FILENAME
    if config_path.exists():
        try:
            with config_path.open(encoding="utf-8") as f:
                data = json.load(f)
            if "tag_sections" in data:
                tag_sections = list(data["tag_sections"])
            if "hidden_tags" in data:
                hidden_tags = list(data["hidden_tags"])
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Warning: Could not parse {CONFIG_FILENAME}: {e}", file=sys.stderr)
    return tag_sections, hidden_tags


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
    parser.add_argument("--title", default="GreyHat Resume Book", help="Cover page title")
    parser.add_argument("--subtitle", default=None, help="Cover page subtitle")
    parser.add_argument(
        "--tag-sections",
        type=str,
        default=None,
        help="Comma-separated tag section titles (e.g. Leadership,Mentor,CTF Competitor). Overrides %s."
        % CONFIG_FILENAME,
    )
    parser.add_argument(
        "--hidden-tags",
        type=str,
        default=None,
        help="Comma-separated tags to hide from badge display (e.g. Leadership). Overrides %s."
        % CONFIG_FILENAME,
    )
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

    # Exclude Fall 1979 (invalid/placeholder grad date)
    candidates = candidates[
        ~candidates["grad_date"].astype(str).str.strip().str.lower().isin(["fall 1979"])
    ].reset_index(drop=True)
    if candidates.empty:
        print("Error: No valid candidates after filtering", file=sys.stderr)
        return 1

    # Filter to only candidates with existing PDFs (page counts must match merged output)
    missing = []
    for _, row in candidates.iterrows():
        fn = str(row["filename"]).strip()
        if not (input_dir / fn).exists():
            missing.append(fn)
    if missing:
        print(f"Excluding {len(missing)} candidates with missing PDFs", file=sys.stderr)
        candidates = candidates[
            candidates["filename"].astype(str).str.strip().apply(
                lambda fn: (input_dir / fn).exists()
            )
        ].reset_index(drop=True)

    if candidates.empty:
        print("Error: No candidates with existing PDFs", file=sys.stderr)
        return 1

    # Tag sections and hidden tags: CLI overrides config file overrides default
    project_root = Path(__file__).resolve().parent.parent
    tag_sections, hidden_tags = load_config(project_root)
    if args.tag_sections is not None:
        tag_sections = [s.strip() for s in args.tag_sections.split(",") if s.strip()]
    if args.hidden_tags is not None:
        hidden_tags = [s.strip() for s in args.hidden_tags.split(",") if s.strip()]

    # Output dir for intermediate files
    out_dir = output_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
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
        generate_typst(
            candidates,
            typ_path,
            args.title,
            args.subtitle,
            tag_sections=tag_sections,
            hidden_tags=hidden_tags,
        )
        if not run_typst_compile(typ_path, cover_toc_path):
            return 1

    # Generate section title pages (one per grad_date group)
    groups = list(candidates.groupby("grad_date", sort=False))
    section_typ_path = out_dir / "section_pages.typ"
    section_pdf_path = out_dir / "section_pages.pdf"
    generate_section_pages_typst(groups, section_typ_path)
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
