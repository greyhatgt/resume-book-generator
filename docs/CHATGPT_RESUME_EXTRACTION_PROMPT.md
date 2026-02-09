# ChatGPT Prompt for Bulk Resume Data Extraction

Use this when you have many resumes to process. Upload the PDFs to ChatGPT (or paste text if PDFs aren't supported), then use the prompt below.

## Batch Prompt (multiple resumes)

Copy and paste this into ChatGPT, then attach your resume files or paste their text:

```
I'm building a resume book. Extract the following fields from each resume and output a CSV.

**CSV columns (use exactly):** filename, name, major, grad_date, email, linkedin, github, phone

**Rules:**
- filename: the original file name (e.g. "John_Doe_Resume.pdf")
- name: full name as it appears on the resume
- major: degree(s) and major (e.g. "B.S. Computer Science", "M.S. Electrical Engineering")
- grad_date: expected graduation to the nearest year + May/Aug/Dec (e.g. "May 2025", "Dec 2024"). Use "Unknown" if not found. If only a year is specified, assume "May". If just a start date is found ("Aug 2025 - Present"), then add 4 years for a Bachelors and 2 for a Masters to get the grad date.
- email: primary email address
- linkedin: full LinkedIn URL (leave empty if not present)
- github: full GitHub URL (leave empty if not present)
- phone: phone number (optional)

**Output format:** CSV with header row, one row per resume. Use commas. Escape any commas in fields with double quotes.

**Resumes:**
Resumes PDFs are attached
```

## Single-Resume Prompt (one at a time)

If ChatGPT accepts one file at a time:

```
Extract the following from this resume and output a single CSV row (no header). Use the exact column order: filename, name, major, grad_date, email, linkedin, github, phone

- filename: [PASTE THE ACTUAL FILENAME e.g. "John_Doe_Resume.pdf"]
- name: full name
- major: degree and major
- grad_date: e.g. "May 2025" or "Unknown"
- email: email address
- linkedin: full URL or empty
- github: full URL or empty
- phone: optional

Output only the CSV row, comma-separated. Quote any field containing a comma.
```

## Workflow

1. Run `uv run python scripts/generate_csv_from_resumes.py --input input-raw --output candidates_template.csv` to get a CSV with filenames and inferred names.
2. Use ChatGPT to extract major, grad_date, email, linkedin, github from each resume.
3. Merge ChatGPT output into your `candidates.csv` (replace the placeholder rows).
4. Copy the CSV header from the template: `filename,name,major,grad_date,email,linkedin,github,phone`
