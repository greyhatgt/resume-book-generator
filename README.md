# Resume Book Generator

Generate a resume book as a single PDF with a terminal-style cover page, table of contents (grouped by graduation date), section title pages between resume groups, and merged resume PDFs. TOC names link to resume pages; section headings (e.g., "Dec 2024") link to their section title pages; LinkedIn and GitHub appear as icons after each name when present. All resume text remains selectable. Uses US Letter paper, GreyHat branding (logo, gray/cyan colors), binary matrix background, and Font Awesome icons.

## Requirements

- Python 3.10+
- [Typst](https://typst.app) CLI (`typst compile`)
- Ghostscript (for PDF merge; optional—falls back to PyMuPDF)
- LibreOffice (for DOCX → PDF conversion; `scripts/convert_docx_to_pdf.py`)
- Typst package: `@preview/fontawesome:0.5.0` (auto-fetched for LinkedIn/GitHub icons)
- `assets/grey_hat_hat_small_400x400.png` (club logo; copied to output when generating)

## Installation

```bash
cd resume-book-generator
uv sync
# or: pip install -e .
```

## Usage

1. Place resume PDFs and DOCX files in `input-raw/`
2. Prepare `input/` (copies PDFs, converts DOCX to PDF, skips duplicates):

```bash
uv run python scripts/prepare_input.py --raw input-raw --output input
```

Or convert DOCX only to a separate folder:

```bash
uv run python scripts/convert_docx_to_pdf.py --input input-raw --output input-pdf
```

3. Generate a template CSV:

```bash
uv run python scripts/generate_csv_from_resumes.py --input input --output candidates.csv
```

`scripts/generate_csv_from_resumes.py` is only a filename/name scaffold. Do not use repo scripts to extract candidate fields from resume text.

4. Fill in `candidates.csv` by manually reviewing the resumes with AI assistance.
   The expected workflow is:
   - use the template CSV only for `filename` and an initial `name`
   - read each resume and manually confirm `name`, `major`, `grad_date`, `email`, `linkedin`, `github`, `phone`, and `tags`
   - keep the reviewed result in `candidates.csv`
   For the current GreyHat workflow, the canonical local file is `candidates.csv`, and `output/manual_review/candidates_manual.csv` is the preserved manual-review copy.
5. Generate the resume book:

```bash
nix-shell -p typst ghostscript libreoffice python313Packages.pandas python313Packages.pymupdf python313Packages.pypdf --run "python scripts/generate_book.py --csv candidates.csv --input input --output output/resume_book.pdf"
```

The local `.venv` currently fails to import `pymupdf` on this machine due to a missing `libstdc++.so.6`, so prefer the Nix Python command above for final builds.

### CSV Schema

| Column    | Required | Description                                                                       |
| --------- | -------- | --------------------------------------------------------------------------------- |
| filename  | yes      | PDF filename (e.g. `john.pdf`)                                                    |
| name      | yes      | Full name                                                                         |
| major     | no       | Degree/major                                                                      |
| grad_date | yes      | Graduation (e.g. `May 2025`)                                                      |
| email     | no       | Email address                                                                     |
| linkedin  | no       | LinkedIn URL (shown as icon after name)                                           |
| github    | no       | GitHub URL (shown as icon after name)                                             |
| phone     | no       | Phone number                                                                      |
| tags      | no       | Comma-separated tags (e.g. `Leadership, Mentors, CTF Competitor`) shown as badges |

Candidates are sorted by `grad_date` then `name`. Use "Unknown" for unknown graduation dates.

Current local normalization rules:

- Names: title case, never all caps
- `Bachelor of Science` -> `B.S.`
- `Master of Science in` -> `M.S. in`
- LinkedIn URLs -> `https://www.linkedin.com/...`
- GitHub URLs -> `https://github.com/...`
- Phone numbers -> `123-456-7890` or `+1 123-456-7890`
- If the resume does not clearly state `grad_date`, keep the old sheet value instead of blanking it
- Preserve sheet `tags`; they are not resume-derived

### Tag sections config

Tags that get a dedicated TOC section (Leadership, Mentor, CTF Competitor, etc.) are configured in `resume_book.json`:

```json
{
  "tag_sections": ["Leadership", "Mentor", "CTF Competitor"],
  "hidden_tags": ["Leadership"]
}
```

- `tag_sections`: Tags that get a dedicated TOC section. Matching is case-insensitive.
- `hidden_tags`: Tags to hide from badge display (e.g. Leadership when already in the Leadership section).

Override via CLI: `--tag-sections "..."` and `--hidden-tags "Leadership"`.

### Sync from Google Drive / Google Sheets

1. Install sync dependencies: `uv sync --extra sync`
2. Sync a Drive folder to `input/`:

```bash
uv run python scripts/sync_drive_to_input.py "https://drive.google.com/drive/folders/FOLDER_ID"
```

3. Sync a Google Sheet to `candidates.csv`:

```bash
uv run python scripts/sync_sheet_to_csv.py "https://docs.google.com/spreadsheets/d/SHEET_ID"
```

- Drive folder must be shared with "Anyone with the link" (or use a different sync tool for private folders).
- Google Sheet: public sheets work without credentials; for private sheets, place service account JSON at `~/.config/gspread/service_account.json` and share the sheet with the service account's `client_email`.
- These sync scripts only move files and tabular data. They are not approved for extracting candidate fields from resumes.

### Manual Review Artifacts

The current repo state includes local-only review artifacts from a manual resume pass:

- `output/manual_review/candidates_manual.csv`: merged manual-review candidate data
- `output/manual_review/chunks/`: per-chunk manual review CSVs
- `output/manual_review/sheet_vs_local_diff.txt`: current diff between the reverted Google Sheet snapshot and the local `candidates.csv`

These are local review outputs; they are not applied back to Google Sheets automatically.

### Options

- `--title`: Cover page title (default: "GreyHat Resume Book")
- `--subtitle`: Cover page subtitle (optional)

## How It Works

For a human-review receipt, isolated build, and validated local release, see
[Reviewed local releases](docs/REVIEWED_BUILDS.md). Deployment remains a separate
operator step until the existing Headstrong service is configured.

1. **Typst** generates cover + TOC (no resume embedding). Names are plain text with optional tag badges and LinkedIn/GitHub icons; section headings link to section title pages.
2. **Section pages**: A separate Typst file generates one title page per graduation group (e.g., "Dec 2024", "May 2025").
3. **Merge**: `cover_toc.pdf` + section title pages + resume PDFs are merged (PyMuPDF, with section pages inserted between groups).
4. **Link injection**: PyMuPDF adds internal link annotations on TOC pages—each name becomes a clickable link to its resume page.
5. Resume text stays selectable because PDFs are merged, not embedded as images.

The current code also fixes a previous TOC-link bug:

- `scripts/generate_book.py` now refreshes the actual TOC page count after the second Typst pass.
- `src/merge/pdf_merger.py` uses the correct 1-based to 0-based page conversion for TOC and section links.

## Project Structure

```
resume-book-generator/
├── assets/                    # Club logo
├── input-raw/                 # Raw resumes (PDF + DOCX)
├── input/                     # Prepared PDFs (from prepare_input)
├── output/                    # cover_toc.typ/pdf, section_pages.typ/pdf, resume_book.pdf
├── docs/
│   └── CHATGPT_RESUME_EXTRACTION_PROMPT.md
├── candidates.csv             # Candidate data
├── src/
│   ├── typst/
│   │   ├── generator.py       # Typst cover + TOC + section page generation
│   │   └── templates/
│   │       ├── cover.typ      # Terminal-style cover template
│   │       └── section_page.typ # Section title page template
│   └── merge/pdf_merger.py    # PDF merge + internal link injection
├── scripts/
│   ├── generate_book.py       # Main CLI
│   ├── prepare_input.py       # Copy PDFs + convert DOCX → input/
│   ├── convert_docx_to_pdf.py  # DOCX to PDF only
│   ├── generate_csv_from_resumes.py # Template CSV from filenames
│   ├── sync_drive_to_input.py # Sync Google Drive folder → input/
│   └── sync_sheet_to_csv.py   # Sync Google Sheet → candidates.csv
├── shell.nix                  # typst, ghostscript, libreoffice
└── pyproject.toml
```

## Data Extraction

Resume-field extraction is intentionally manual AI-assisted review, not repo automation.

- Use [docs/CHATGPT_RESUME_EXTRACTION_PROMPT.md](docs/CHATGPT_RESUME_EXTRACTION_PROMPT.md) as a review prompt.
- Read the actual resumes and confirm each row before treating it as canonical.
- Do not rely on repo scripts to infer `major`, `grad_date`, contact links, or tags from resume text.
