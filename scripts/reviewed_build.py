#!/usr/bin/env python3
"""Record human review, then build a private, validated release without deploying it."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent.parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(csv_path: Path, input_dir: Path) -> dict:
    """Reject rows the legacy generator would silently omit, without extracting fields."""
    input_dir = input_dir.resolve(strict=True)
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"filename", "name", "grad_date"}.issubset(reader.fieldnames or []):
            raise ValueError("Missing required CSV columns")
        files = {}
        for row in reader:
            if any(not (row.get(key) or "").strip() for key in ("filename", "name", "grad_date")):
                raise ValueError("Every candidate needs filename, name, and grad_date")
            if row["grad_date"].strip().lower() == "fall 1979":
                raise ValueError("Replace placeholder graduation dates during human review")
            name = row["filename"].strip()
            if name in files or name.casefold() in {key.casefold() for key in files}:
                raise ValueError("Duplicate resume filename")
            # Flat names work consistently on both Windows and the deployment host.
            if Path(name).name != name or any(c in name for c in "/\\:") or not name.lower().endswith(".pdf"):
                raise ValueError("Resume filenames must be plain PDF filenames")
            path = input_dir / name
            if path.is_symlink() or path.resolve().parent != input_dir or not path.is_file():
                raise ValueError("A reviewed resume is missing or outside the input folder")
            files[name] = digest(path)
    if not files:
        raise ValueError("The reviewed candidate list is empty")
    return {"csv_sha256": digest(csv_path), "resumes": files}


def record_review(csv_path: Path, input_dir: Path, receipt: Path, reviewer: str) -> None:
    if not reviewer.strip():
        raise ValueError("A reviewer identifier is required")
    data = {"schema": 1, "reviewer": reviewer.strip(),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "inputs": inventory(csv_path, input_dir)}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    # Do not silently replace an earlier review receipt.
    with receipt.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def validate_pdf(output_dir: Path, csv_path: Path, input_dir: Path) -> dict:
    import pymupdf
    sys.path.insert(0, str(ROOT))
    from src.typst.generator import load_candidates, compute_page_offsets

    candidates = load_candidates(csv_path, input_dir)
    if len(candidates) != len(inventory(csv_path, input_dir)["resumes"]):
        raise ValueError("Generator omitted a reviewed candidate")
    with pymupdf.open(output_dir / "cover_toc.pdf") as cover:
        cover_pages = len(cover)
    with pymupdf.open(output_dir / "section_pages.pdf") as sections:
        section_pages = len(sections)
    groups = candidates["grad_date"].nunique()
    if cover_pages < 2 or section_pages != groups:
        raise ValueError("Unexpected cover/TOC or section page count")
    resume_pages = 0
    for name in candidates["filename"]:
        with pymupdf.open(input_dir / str(name).strip()) as resume:
            if resume.needs_pass or not len(resume):
                raise ValueError("An input PDF is empty or encrypted")
            resume_pages += len(resume)
    offsets = compute_page_offsets(candidates, input_dir, cover_pages)
    expected_outline = [(str(row["name"]).strip(), offsets[str(row["filename"]).strip()])
                        for _, row in candidates.iterrows()]
    with pymupdf.open(output_dir / "resume_book.pdf") as book:
        if book.needs_pass or len(book) != cover_pages + section_pages + resume_pages:
            raise ValueError("Final PDF page count mismatch or encryption")
        actual_outline = [(entry[1], entry[2]) for entry in book.get_toc() if entry[0] == 3]
        if actual_outline != expected_outline:
            raise ValueError("Final PDF candidate outline mismatch")
        linked_pages = set()
        for index, page in enumerate(book):
            page.get_text()  # Force parsing every page, without writing candidate text to logs.
            for link in page.get_links():
                if link["kind"] == pymupdf.LINK_GOTO:
                    target = link.get("page", -1)
                    if not 0 <= target < len(book):
                        raise ValueError("Final PDF contains an invalid internal link")
                    if index < cover_pages:
                        linked_pages.add(target + 1)
        if not set(offsets.values()).issubset(linked_pages):
            raise ValueError("TOC is missing a link to a candidate resume")
        return {"pages": len(book), "candidates": len(candidates), "sections": groups}


@contextmanager
def release_lock(release: Path):
    """Serialize cooperating builders; never remove another builder's lock."""
    release.parent.mkdir(parents=True, exist_ok=True)
    lock = release.parent / ("." + release.name + ".build-lock")
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("Release is locked by another build; check it before removing a stale lock") from None
    try:
        yield
    finally:
        lock.rmdir()


def build(csv_path: Path, input_dir: Path, receipt: Path, release: Path) -> None:
    release = release.resolve()
    with release_lock(release):
        _build_locked(csv_path, input_dir, receipt, release)


def _build_locked(csv_path: Path, input_dir: Path, receipt: Path, release: Path) -> None:
    review = json.loads(receipt.read_text(encoding="utf-8"))
    if review.get("schema") != 1 or not review.get("reviewer") or not review.get("reviewed_at"):
        raise ValueError("Invalid human-review receipt")
    if review.get("inputs") != inventory(csv_path, input_dir):
        raise ValueError("Inputs changed since human review; review them again")
    release = release.resolve()
    if release.exists():
        raise ValueError("Release directory already exists; use a new release name")
    release.parent.mkdir(parents=True, exist_ok=True)
    # Staging beside the release allows an atomic directory rename on the same filesystem.
    with tempfile.TemporaryDirectory(prefix=".reviewed-build-", dir=release.parent) as temporary:
        stage = Path(temporary)
        staged_input = stage / "input"
        staged_input.mkdir()
        staged_csv = stage / "candidates.csv"
        shutil.copyfile(csv_path, staged_csv)
        for name in review["inputs"]["resumes"]:
            shutil.copyfile(input_dir / name, staged_input / name)
        if inventory(staged_csv, staged_input) != review["inputs"]:
            raise ValueError("Inputs changed while preparing the build")
        output = stage / "release"
        output.mkdir()
        # Build logs can contain candidate filenames; keep them inside the private stage.
        with (output / "build.log").open("w", encoding="utf-8") as log:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/generate_book.py"),
                                     "--csv", str(staged_csv), "--input", str(staged_input),
                                     "--output", str(output / "resume_book.pdf")],
                                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError("Generator failed; no release published (private temporary logs removed)")
        validation = validate_pdf(output, staged_csv, staged_input)
        manifest = {"schema": 1, "review": review, "validation": validation,
                    "built_at": datetime.now(timezone.utc).isoformat(),
                    "pdf_sha256": digest(output / "resume_book.pdf")}
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if release.exists():
            raise ValueError("Release directory appeared during build; refusing replacement")
        os.rename(output, release)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["review", "build"])
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--reviewer", help="Human who has finished metadata review")
    parser.add_argument("--confirm-reviewed", action="store_true", help="Explicit human-review attestation")
    parser.add_argument("--release", type=Path, help="New private local release directory")
    args = parser.parse_args()
    try:
        if args.action == "review":
            if not args.confirm_reviewed or not args.reviewer:
                parser.error("review requires --reviewer and --confirm-reviewed")
            record_review(args.csv, args.input, args.receipt, args.reviewer)
        else:
            if args.release is None:
                parser.error("build requires --release")
            build(args.csv, args.input, args.receipt, args.release)
    except (ValueError, OSError) as error:
        # OS errors can contain private candidate paths, so expose only a generic diagnostic.
        print(str(error) if isinstance(error, ValueError) else "File access failed; no release published", file=sys.stderr)
        return 1
    print("Review recorded" if args.action == "review" else "Validated local release created; deployment still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
