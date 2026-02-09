"""Merge PDFs, preserving internal and external links."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf


def _merge_with_pymupdf(pdf_paths: list[Path], output_path: Path) -> None:
    """Merge using PyMuPDF."""
    merged = pymupdf.open()
    try:
        for path in pdf_paths:
            doc = pymupdf.open(path)
            try:
                merged.insert_pdf(doc, links=True, annots=True)
            finally:
                doc.close()
        merged.save(str(output_path))
    finally:
        merged.close()


def get_pdf_page_count(pdf_path: Path) -> int:
    """Return the number of pages in a PDF file."""
    doc = pymupdf.open(pdf_path)
    try:
        return len(doc)
    finally:
        doc.close()


def _merge_with_ghostscript(pdf_paths: list[Path], output_path: Path) -> bool:
    """Merge using Ghostscript. Returns True if successful."""
    gs = shutil.which("gs")
    if not gs:
        return False
    args = [
        gs,
        "-q",
        "-dNOPAUSE",
        "-dBATCH",
        "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=/default",
        f"-sOutputFile={output_path}",
        *[str(p) for p in pdf_paths],
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode == 0


def merge_pdfs(
    pdf_paths: list[Path],
    output_path: Path,
) -> None:
    """Merge PDFs in order into a single file. Tries Ghostscript first for external links."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Ghostscript for merge (external links work)
    if _merge_with_ghostscript(pdf_paths, output_path):
        return

    _merge_with_pymupdf(pdf_paths, output_path)


def merge_pdfs_with_sections(
    cover_toc_path: Path,
    section_pages_path: Path,
    resume_paths_by_group: list[list[Path]],
    output_path: Path,
) -> None:
    """Merge cover_toc, then for each group: section title page, then resumes.
    Uses PyMuPDF to insert specific pages from section_pages_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged = pymupdf.open()
    try:
        # Insert cover + TOC
        cover_doc = pymupdf.open(cover_toc_path)
        try:
            merged.insert_pdf(cover_doc, links=True, annots=True)
        finally:
            cover_doc.close()
        # Insert section title + resumes for each group
        section_doc = pymupdf.open(section_pages_path)
        try:
            for i, resume_paths in enumerate(resume_paths_by_group):
                if i < len(section_doc):
                    merged.insert_pdf(section_doc, from_page=i, to_page=i, links=True, annots=True)
                for p in resume_paths:
                    if p.exists():
                        doc = pymupdf.open(p)
                        try:
                            merged.insert_pdf(doc, links=True, annots=True)
                        finally:
                            doc.close()
        finally:
            section_doc.close()
        merged.save(str(output_path))
    finally:
        merged.close()


def set_pdf_outline(
    pdf_path: Path,
    sections: list[tuple[str, int, list[tuple[str, int]]]],
    cover_toc_page_count: int,
) -> None:
    """Add PDF outline/bookmarks so the native TOC shows sections and names.

    sections: list of (grad_date, section_page_0based, [(name, page_0based), ...])
    """
    doc = pymupdf.open(pdf_path)
    try:
        toc: list[tuple[int, str, int]] = []
        toc.append((1, "Cover", 0))
        if cover_toc_page_count > 1:
            toc.append((1, "Table of Contents", 1))

        for label, section_page, name_pages in sections:
            toc.append((2, label, section_page))
            for name, page in name_pages:
                toc.append((3, name, page))

        doc.set_toc(toc)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            doc.save(str(tmp_path), incremental=False)
            doc.close()
            shutil.move(str(tmp_path), str(pdf_path))
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
    finally:
        if "doc" in dir() and not doc.is_closed:
            doc.close()


def add_internal_links(
    pdf_path: Path,
    candidates: list[tuple[str, int]],
    cover_toc_page_count: int,
    section_links: list[tuple[str, int]] | None = None,
) -> None:
    """Add internal link annotations on TOC pages. Each name links to the given page number.
    Section headings (e.g. grad_date) link to their section title pages.

    candidates: list of (name, target_page_1based)
    cover_toc_page_count: total pages of cover+toc (cover=1, rest is TOC)
    section_links: list of (section_label, target_page_1based) for TOC section headings
    """
    doc = pymupdf.open(pdf_path)
    try:
        toc_start = 1
        toc_end = cover_toc_page_count

        for name, target_page in candidates:
            # target_page is 1-based; PyMuPDF uses 0-indexed
            target_page_idx = max(0, target_page - 2)
            if target_page_idx < 0 or target_page_idx >= len(doc):
                continue

            found = False
            for page_num in range(toc_start, toc_end):
                if page_num >= len(doc):
                    break
                page = doc[page_num]
                rects = page.search_for(name, quads=False)
                if rects:
                    # Use first match; link to top of target page (PDF coords: y increases upward)
                    dest_page = doc[target_page_idx]
                    mb = dest_page.mediabox
                    top_left = pymupdf.Point(mb.x0, mb.y1)
                    link = {
                        "kind": pymupdf.LINK_GOTO,
                        "from": rects[0],
                        "page": target_page_idx,
                        "to": top_left,
                    }
                    page.insert_link(link)
                    found = True
                if found:
                    break

        # Add section heading links after name links - go to page before first resume (section title)
        for label, target_page in section_links or []:
            target_page_idx = max(0, target_page - 3)
            if target_page_idx < 0 or target_page_idx >= len(doc):
                continue
            for page_num in range(toc_start, toc_end):
                if page_num >= len(doc):
                    break
                page = doc[page_num]
                rects = page.search_for(label, quads=False)
                if rects:
                    dest_page = doc[target_page_idx]
                    mb = dest_page.mediabox
                    top_left = pymupdf.Point(mb.x0, mb.y1)
                    link = {
                        "kind": pymupdf.LINK_GOTO,
                        "from": rects[0],
                        "page": target_page_idx,
                        "to": top_left,
                    }
                    page.insert_link(link)
                    break
    finally:
        # Save to temp file then replace (Ghostscript output may not support incremental)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            doc.save(str(tmp_path), incremental=False)
            doc.close()
            shutil.move(str(tmp_path), str(pdf_path))
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
