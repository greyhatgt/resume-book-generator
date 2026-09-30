"""Offline tests use synthetic candidate metadata and PDFs only."""
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch

import pymupdf

from scripts import reviewed_build as pipeline


class ReviewedBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.inputs.mkdir()
        self.csv = self.root / "candidates.csv"
        self.csv.write_text("filename,name,grad_date\nalex.pdf,Alex Example,May 2027\n", encoding="utf-8")
        self.make_pdf(self.inputs / "alex.pdf", 1)
        self.receipt = self.root / "review.json"
        pipeline.record_review(self.csv, self.inputs, self.receipt, "Synthetic Reviewer")
        self.release = self.root / "release"

    def make_pdf(self, path, pages):
        with pymupdf.open() as document:
            for number in range(pages):
                document.new_page().insert_text((50, 50), f"Synthetic page {number}")
            document.save(path)

    def fake_generator(self, command, **kwargs):
        folder = Path(command[command.index("--output") + 1]).parent
        self.make_pdf(folder / "cover_toc.pdf", 2)
        self.make_pdf(folder / "section_pages.pdf", 1)
        self.make_pdf(folder / "resume_book.pdf", 4)
        with pymupdf.open(folder / "resume_book.pdf") as document:
            document.set_toc([[1, "Table of Contents", 2], [2, "May 2027", 3], [3, "Alex Example", 4]])
            document[1].insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(50, 50, 150, 65), "page": 3})
            document.saveIncr()
        return subprocess.CompletedProcess(command, 0)

    def test_changed_metadata_or_resume_requires_review(self):
        for path in (self.csv, self.inputs / "alex.pdf"):
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "changed since human review"):
                pipeline.build(self.csv, self.inputs, self.receipt, self.release)
            path.write_bytes(original)
        self.assertFalse(self.release.exists())

    def test_bad_rows_rejected(self):
        rows = ["../alex.pdf,Alex Example,May 2027", "alex.pdf,,May 2027",
                "alex.pdf,Alex Example,Fall 1979", "missing.pdf,Alex Example,May 2027",
                "alex.pdf,Alex Example,May 2027\nalex.pdf,Other Example,May 2027"]
        for row in rows:
            with self.subTest(row=row):
                self.csv.write_text("filename,name,grad_date\n" + row + "\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    pipeline.inventory(self.csv, self.inputs)

    def test_success_publishes_validated_release_with_hash(self):
        with patch.object(pipeline.subprocess, "run", side_effect=self.fake_generator):
            pipeline.build(self.csv, self.inputs, self.receipt, self.release)
        manifest = json.loads((self.release / "manifest.json").read_text())
        self.assertEqual(manifest["validation"], {"pages": 4, "candidates": 1, "sections": 1})
        self.assertEqual(manifest["pdf_sha256"], pipeline.digest(self.release / "resume_book.pdf"))
        self.assertFalse(list(self.root.glob(".reviewed-build-*")))

    def test_generator_failure_keeps_existing_release(self):
        self.release.mkdir()
        existing = self.release / "resume_book.pdf"
        existing.write_bytes(b"previous release")
        next_release = self.root / "next-release"
        with patch.object(pipeline.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(ValueError, "Generator failed"):
                pipeline.build(self.csv, self.inputs, self.receipt, next_release)
        self.assertEqual(existing.read_bytes(), b"previous release")
        self.assertFalse(next_release.exists())

    def test_invalid_pdf_does_not_publish(self):
        def bad_generator(command, **kwargs):
            result = self.fake_generator(command, **kwargs)
            folder = Path(command[command.index("--output") + 1]).parent
            (folder / "resume_book.pdf").unlink()
            self.make_pdf(folder / "resume_book.pdf", 3)
            return result
        with patch.object(pipeline.subprocess, "run", side_effect=bad_generator):
            with self.assertRaisesRegex(ValueError, "page count"):
                pipeline.build(self.csv, self.inputs, self.receipt, self.release)
        self.assertFalse(self.release.exists())

    def test_missing_toc_link_blocks_publication(self):
        def bad_generator(command, **kwargs):
            result = self.fake_generator(command, **kwargs)
            pdf = Path(command[command.index("--output") + 1])
            with pymupdf.open(pdf) as document:
                for link in document[1].get_links():
                    document[1].delete_link(link)
                document.saveIncr()
            return result
        with patch.object(pipeline.subprocess, "run", side_effect=bad_generator):
            with self.assertRaisesRegex(ValueError, "TOC is missing"):
                pipeline.build(self.csv, self.inputs, self.receipt, self.release)

    def test_existing_release_and_review_cannot_be_overwritten(self):
        with self.assertRaises(FileExistsError):
            pipeline.record_review(self.csv, self.inputs, self.receipt, "Someone Else")
        self.release.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            pipeline.build(self.csv, self.inputs, self.receipt, self.release)

    def test_concurrent_build_refuses_owned_lock(self):
        with pipeline.release_lock(self.release):
            with self.assertRaisesRegex(ValueError, "locked by another build"):
                pipeline.build(self.csv, self.inputs, self.receipt, self.release)
            self.assertTrue((self.root / ".release.build-lock").is_dir())
        self.assertFalse((self.root / ".release.build-lock").exists())

    @unittest.skipUnless(shutil.which("typst"), "Typst is needed for the actual generator integration test")
    def test_actual_generator_with_two_synthetic_candidates(self):
        self.make_pdf(self.inputs / "sam.pdf", 2)
        self.csv.write_text("filename,name,grad_date\nalex.pdf,Alex Example,May 2027\n"
                            "sam.pdf,Sam Example,Dec 2027\n", encoding="utf-8")
        next_receipt = self.root / "second-review.json"
        pipeline.record_review(self.csv, self.inputs, next_receipt, "Synthetic Reviewer")
        pipeline.build(self.csv, self.inputs, next_receipt, self.release)
        manifest = json.loads((self.release / "manifest.json").read_text())
        self.assertEqual(manifest["validation"]["candidates"], 2)
        self.assertEqual(manifest["validation"]["sections"], 2)

    def test_candidate_and_section_links_use_correct_zero_based_pages(self):
        from src.merge.pdf_merger import add_internal_links
        pdf = self.root / "links.pdf"
        with pymupdf.open() as document:
            for _ in range(4):
                document.new_page()
            document[1].insert_text((50, 50), "May 2027")
            document[1].insert_text((50, 75), "Alex Example")
            document.save(pdf)
        add_internal_links(pdf, [("Alex Example", 4)], 2, [("May 2027", 4)])
        with pymupdf.open(pdf) as document:
            links = document[1].get_links()
            self.assertEqual({link["page"] for link in links}, {2, 3})
            self.assertTrue(all(link["to"] == pymupdf.Point(0, 0) for link in links))


if __name__ == "__main__":
    unittest.main()
