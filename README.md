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

4. Edit `candidates.csv` to fill in `major`, `grad_date`, `email`, `linkedin`, `github`. Use the [ChatGPT prompt](docs/CHATGPT_RESUME_EXTRACTION_PROMPT.md) to extract data from resumes in bulk.
5. Generate the resume book:

```bash
nix-shell --run "uv run python scripts/generate_book.py --csv candidates.csv --input input --output output/resume_book.pdf"
```

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

### Options

- `--title`: Cover page title (default: "GreyHat Resume Book")
- `--subtitle`: Cover page subtitle (optional)

## How It Works

1. **Typst** generates cover + TOC (no resume embedding). Names are plain text with optional tag badges and LinkedIn/GitHub icons; section headings link to section title pages.
2. **Section pages**: A separate Typst file generates one title page per graduation group (e.g., "Dec 2024", "May 2025").
3. **Merge**: `cover_toc.pdf` + section title pages + resume PDFs are merged (PyMuPDF, with section pages inserted between groups).
4. **Link injection**: PyMuPDF adds internal link annotations on TOC pages—each name becomes a clickable link to its resume page.
5. Resume text stays selectable because PDFs are merged, not embedded as images.

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
│   ├── convert_docx_to_pdf.py # DOCX to PDF only
│   └── generate_csv_from_resumes.py # Template CSV from filenames
├── shell.nix                  # typst, ghostscript, libreoffice
└── pyproject.toml
```

## Data Extraction

To populate the CSV from resume text, use the [ChatGPT prompt](docs/CHATGPT_RESUME_EXTRACTION_PROMPT.md) for bulk extraction. Upload your resumes to ChatGPT and paste the prompt; it will output CSV rows you can merge into `candidates.csv`.
