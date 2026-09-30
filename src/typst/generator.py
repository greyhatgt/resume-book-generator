"""Generate Typst cover + TOC document from candidate CSV."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..merge.pdf_merger import get_pdf_page_count

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _escape_typst_string(s: str) -> str:
    """Escape a string for use inside Typst string literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _grad_date_sort_key(grad_date: str) -> tuple[int, int]:
    """Convert grad_date to (year, month) for sorting. 'Unknown' sorts last."""
    if not grad_date or str(grad_date).strip().lower() == "unknown":
        return (9999, 99)
    s = str(grad_date).strip()
    # Try to parse "May 2025", "Dec 2024", "2025", "Spring 2025"
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "spring": 5, "summer": 8, "fall": 11, "winter": 2,
    }
    parts = s.lower().replace(",", " ").split()
    year = 0
    month = 0
    for p in parts:
        if p.isdigit() and len(p) == 4:
            year = int(p)
        elif p in months:
            month = months[p]
    if year == 0:
        year = 9999
    if month == 0:
        month = 1
    return (year, month)


def load_candidates(csv_path: Path, input_dir: Path) -> pd.DataFrame:
    """Load and validate candidates from CSV. Returns sorted DataFrame."""
    df = pd.read_csv(csv_path)
    required = {"filename", "name", "grad_date"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    # Drop rows with missing required fields
    df = df.dropna(subset=["filename", "name", "grad_date"])
    df = df[df["filename"].astype(str).str.strip() != ""]
    df = df[df["name"].astype(str).str.strip() != ""]
    df = df[df["grad_date"].astype(str).str.strip() != ""]

    # Fill missing optional columns
    for col in ["major", "email", "linkedin", "github", "phone", "tags"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    # Normalize grad_date for display
    df["grad_date"] = df["grad_date"].astype(str).str.strip()
    df.loc[df["grad_date"].str.lower() == "unknown", "grad_date"] = "Unknown"

    # Sort by grad_date then name
    df = df.assign(_sort_key=df["grad_date"].apply(_grad_date_sort_key))
    df = df.sort_values(["_sort_key", "name"])
    df = df.drop(columns=["_sort_key"])

    return df.reset_index(drop=True)


def compute_page_offsets(
    candidates: pd.DataFrame,
    input_dir: Path,
    cover_toc_page_count: int,
) -> dict[str, int]:
    """Compute starting page number for each candidate in the final merged PDF.

    With section pages: merge order is cover_toc, then for each group:
    section_title_page, resumes...
    """
    # First resume starts after cover_toc + section page for first group
    current_page = cover_toc_page_count + 1  # first section page (1-based)
    offsets: dict[str, int] = {}
    groups = candidates.groupby("grad_date", sort=False)
    for _, group_df in groups:
        current_page += 1  # section title page
        for _, row in group_df.iterrows():
            fn = str(row["filename"]).strip()
            path = input_dir / fn
            if path.exists():
                count = get_pdf_page_count(path)
            else:
                count = 1  # assume 1 if missing
            offsets[fn] = current_page
            current_page += count
    return offsets


def compute_section_page_numbers(
    candidates: pd.DataFrame,
    input_dir: Path,
    cover_toc_page_count: int,
) -> dict[str, int]:
    """Compute 1-based page for each section. Returns first-resume page; add_internal_links uses -2 to land on section title."""
    section_pages: dict[str, int] = {}
    current_page = cover_toc_page_count + 1  # first section page (1-based)
    groups = candidates.groupby("grad_date", sort=False)
    for grad_date, group_df in groups:
        grad_str = str(grad_date).strip()
        section_pages[grad_str] = current_page + 1  # first resume, 1-based; link uses -2 for section title
        current_page += 1  # section page
        for _, row in group_df.iterrows():
            fn = str(row["filename"]).strip()
            path = input_dir / fn
            if path.exists():
                current_page += get_pdf_page_count(path)
            else:
                current_page += 1
    return section_pages


# Club colors
_CYAN = 'rgb("#00bcd4")'
_GRAY = 'rgb("#525252")'


def _ensure_templates_in_output_dir(output_dir: Path) -> None:
    """Copy Typst templates to output dir so #include resolves."""
    for name in ["cover.typ", "section_page.typ"]:
        src = _TEMPLATES_DIR / name
        dst = output_dir / name
        if src.exists():
            shutil.copy2(src, dst)


DEFAULT_TAG_SECTIONS: list[str] = ["Leadership", "Mentor", "CTF Competitor"]


def generate_typst(
    candidates: pd.DataFrame,
    output_path: Path,
    title: str = "GreyHat Resume Book",
    subtitle: str | None = None,
    tag_sections: list[str] | None = None,
    hidden_tags: list[str] | None = None,
) -> str:
    """Generate Typst source and write to output_path. Returns the generated content."""
    if tag_sections is None:
        tag_sections = DEFAULT_TAG_SECTIONS
    if hidden_tags is None:
        hidden_tags = []

    # Set of lowercase tag substrings to hide from badge display
    hidden_tags_lower = {t.lower().strip() for t in hidden_tags}

    out_dir = output_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    _ensure_templates_in_output_dir(out_dir)

    title_esc = _escape_typst_string(title)
    subtitle_esc = _escape_typst_string(subtitle if subtitle is not None else "")

    # Pass release/build from Python (Typst datetime.today() bug returns 1979/1980)
    d = datetime.today()
    m = d.month
    term = "Spring" if m <= 5 else "Summer" if m <= 8 else "Fall"
    release = f"{term} {d.year}"
    build = d.strftime("%Y.%m.%d")

    lines: list[str] = [
        "// Generated by resume-book-generator",
        "",
        '#import "@preview/fontawesome:0.5.0": *',
        "",
        '#set page(margin: 1in, paper: "us-letter")',
        "#set text(size: 11pt)",
        "",
        "// Cover page",
        '#import "cover.typ": cover',
        f'#cover("{title_esc}", "{subtitle_esc}", {len(candidates)}, "{release}", "{build}")',
        "",
        "#set page(fill: white, background: none)",
        "",
        "",
        "// Table of contents",
        "#pagebreak()",
        f"#text(size: 32pt, weight: \"bold\")[Table of Contents]",
        "#v(-2em)",
        f"#text(size: 9pt, fill: {_GRAY})[Section titles, names, and LinkedIn/GitHub icons are clickable.]",
        "#v(1em)",
        "",
    ]

    # Tag sections at top (names link to same resume pages)
    def _append_section_table(
        rows_df: pd.DataFrame,
        include_trailing: bool = True,
        right_column: str = "major",
    ) -> None:
        right_header = "*Graduation Date*" if right_column == "grad_date" else "*Major*"
        lines.append(
            "#table("
            "columns: (1fr, 1fr),"
            "stroke: none,"
            "inset: 8pt,"
            "align: (left, right),"
            "fill: (x, y) => if y == 0 { rgb(\"#c0c0c0\") } else if calc.rem(y, 2) == 1 { white } else { rgb(\"#f5f5f5\") },"
        )
        lines.append(f"  table.header([*Name*], [{right_header}],),")
        for _, row in rows_df.iterrows():
            name = _escape_typst_string(str(row["name"]))
            right_val = _escape_typst_string(
                str(row.get("grad_date" if right_column == "grad_date" else "major", "") or "")
            )
            linkedin_raw = str(row.get("linkedin", "") or "").strip()
            github_raw = str(row.get("github", "") or "").strip()
            tags_raw = str(row.get("tags", "") or "").strip()
            tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
            badge_parts = []
            for tag in tags_list:
                if tag.lower().strip() in hidden_tags_lower:
                    continue
                tag_esc = _escape_typst_string(tag)
                badge_parts.append(
                    f'#box(fill: {_CYAN}, inset: (x: 4pt, y: 2pt), radius: 4pt, baseline: 10%)[#text(size: 8pt, fill: rgb("#323232"))[{tag_esc}]]'
                )
            badges = " ".join(badge_parts)
            icon_parts = []
            if linkedin_raw and linkedin_raw.startswith("http"):
                icon_parts.append(f'#link("{_escape_typst_string(linkedin_raw)}")[#fa-linkedin(size: 9pt)]')
            if github_raw and github_raw.startswith("http"):
                icon_parts.append(f'#link("{_escape_typst_string(github_raw)}")[#fa-github(size: 9pt)]')
            icons = " ".join(icon_parts)
            name_parts = [
                # "#fa-link(size: 7pt)", 
                # "#h(0.1em)", 
                f'#text("{name}")'
            ]
            if icons:
                name_parts.append(icons)
            if badges:
                name_parts.append(badges)
            name_cell = " ".join(name_parts)
            lines.append(f"  [{name_cell}], [#text(\"{right_val}\")],")
        lines.append(")")
        if include_trailing:
            lines.append("#v(1em)")
            lines.append("")

    for section_title in tag_sections:
        tag_substring = section_title.lower().strip()
        section_df = candidates[
            candidates["tags"].astype(str).str.lower().str.contains(tag_substring, na=False)
        ]
        if not section_df.empty:
            title_esc = _escape_typst_string(section_title)
            lines.append("#block(breakable: false)[")
            lines.append(f"#text(size: 14pt, weight: \"bold\", fill: {_CYAN})[{title_esc}]")
            lines.append("#v(-0.5em)")
            _append_section_table(section_df, include_trailing=False, right_column="grad_date")
            lines.append("]")
            lines.append("#v(1em)")
            lines.append("")

    # Group by grad_date; TOC stays on one page; section headings are plain text (links added via PyMuPDF)
    groups = list(candidates.groupby("grad_date", sort=False))
    for grad_date, group_df in groups:
        grad_display = _escape_typst_string(str(grad_date))
        lines.append(f"#text(size: 14pt, weight: \"bold\", fill: {_CYAN})[#fa-link(size: 10pt) {grad_display}]")
        lines.append("#v(-0.5em)")
        _append_section_table(group_df, include_trailing=False)
        lines.append("#v(1em)")
        lines.append("")

    content = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return content


def generate_section_pages_typst(
    groups: list[tuple[str, pd.DataFrame]],
    output_path: Path,
) -> str:
    """Generate Typst source for section title pages (one page per grad date)."""
    out_dir = output_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    _ensure_templates_in_output_dir(out_dir)

    d = datetime.today()
    m = d.month
    term = "Spring" if m <= 5 else "Summer" if m <= 8 else "Fall"
    release = f"{term} {d.year}"
    build = d.strftime("%Y.%m.%d")

    lines: list[str] = [
        "// Generated by resume-book-generator (section pages)",
        "",
        '#set page(margin: 1in, paper: "us-letter")',
        "#set text(size: 11pt)",
        "",
        '#import "section_page.typ": section-page',
        "",
    ]
    for i, (grad_date, group_df) in enumerate(groups):
        if i > 0:
            lines.append("#pagebreak()")
        grad_esc = _escape_typst_string(str(grad_date))
        count = len(group_df)
        release_esc = _escape_typst_string(release)
        build_esc = _escape_typst_string(build)
        lines.append(f'#section-page("{grad_esc}", {count}, "{release_esc}", "{build_esc}")')
    content = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return content
