# Repo Notes

## Build

- Prefer the Nix shell for all book-generation work.
- The checked-in `.venv` currently fails to import `pymupdf` on this machine with `libstdc++.so.6` missing, so do not rely on `uv run` for the final book build.
- Use this command to generate the book:

```bash
nix-shell -p typst ghostscript libreoffice python313Packages.pandas python313Packages.pymupdf python313Packages.pypdf --run "python scripts/generate_book.py --csv candidates.csv --input input --output output/resume_book.pdf"
```

## Candidate Data

- `candidates.csv` is the active local candidate file used by the generator.
- `output/manual_review/candidates_manual.csv` is the preserved manual-review copy.
- `output/manual_review/chunks/` contains the chunk CSVs from the manual resume review pass.
- `output/manual_review/sheet_vs_local_diff.txt` is the current local diff report against the reverted Google Sheet snapshot.
- Resume-field extraction is manual AI-assisted review, not repo automation.
- `scripts/generate_csv_from_resumes.py` may be used only to scaffold filenames and initial names.
- Do not use repo scripts as the source of truth for `major`, `grad_date`, `email`, `linkedin`, `github`, `phone`, or `tags`; those must come from manual resume review or the reviewed sheet.

## Data Rules

- Keep names in title case, never all caps.
- Normalize `Bachelor of Science` wording to `B.S.`.
- Normalize `Master of Science in` wording to `M.S. in`.
- Normalize phone numbers to `123-456-7890` or `+1 123-456-7890`.
- Normalize LinkedIn URLs to `https://www.linkedin.com/...`.
- Normalize GitHub URLs to `https://github.com/...`.
- Keep the old sheet `grad_date` when the resume does not clearly provide one.
- Preserve existing sheet `tags`; they are not resume-derived.

## Link Behavior

- TOC links were previously wrong because `scripts/generate_book.py` reused a stale TOC page count after the second Typst pass, and `src/merge/pdf_merger.py` had an off-by-one conversion from 1-based page numbers to PyMuPDF's 0-based page indexes.
- If TOC links ever look wrong again, verify the actual generated `output/resume_book.pdf`, not a cached editor preview.
