---
name: minicheck-report
description: Run SAP HANA MiniCheck against the on-prem system and generate a TPO-format Word report with findings and recommendations
argument-hint: [output-filename.docx]
---

Run a SAP HANA MiniCheck analysis against the on-prem HANA system and generate a Word report in TPO format.

## Steps

### 1. Execute the MiniCheck
Run the MiniCheck SQL file against the on-prem HANA system:
- Tool: `mcp__sap-hana-onprem__execute_sql_file`
- File path: `/Users/I321356/Documents/claude_project/HANA_Configuration_MiniChecks.txt`

### 2. Parse and summarize critical findings
From the results, extract all rows where `C = 'X'` (potentially critical).
Present a summary table with columns: CHID | Description | Value | Expected | SAP Note.

### 3. Generate the Word report
Determine the output filename:
- If `$ARGUMENTS` is provided, use it as the output filename (resolve relative to `/Users/I321356/Documents/claude_project/` if not absolute)
- Otherwise default to `/Users/I321356/Documents/claude_project/MiniCheck_Report.docx`

Run the report generator:
```
/Users/I321356/Documents/claude_project/sap-hana-mcp/.venv/bin/python \
  /Users/I321356/Documents/claude_project/generate_minicheck_report.py \
  <output_path>
```

### 4. Post-process the report
After generation, apply these fixes to the output .docx file using python-docx
(python at `/Users/I321356/Documents/claude_project/sap-hana-mcp/.venv/bin/python`):

**a) Filter to only the sections matching critical findings (C=X)**
Keep only Heading 2 sections whose title matches one of the critical findings.
Order them by MiniCheck CHID ascending.

**b) Prepend document structure from TPO template**
Copy these sections verbatim from `/Users/I321356/Documents/claude_project/TPO_template.docx`:
- Cover page (everything before Table of Contents heading)
- Table of Contents heading
- Service Summary (H1) with Executive Summary and Action Plan subsections
- General Overview (H1) with all subsections
- Check Lists (H1) with all subsections
- Issues and Recommendations (H1) heading

**c) Replace static ToC with Word automatic TOC field**
Remove static ToC entries and insert a `TOC \o "1-3" \h \z \u` field so Word
auto-generates the table of contents when the file is opened.

**d) Fix the Action Plan table**
In the Action Plan section, keep only the table rows whose Issue column matches
one of the critical findings. Renumber the ID column sequentially from 1.

### 5. Report results
Tell the user:
- Total checks run
- Number of critical findings (C=X)
- Summary table of all critical findings
- Path to the generated Word report
- Reminder to press Ctrl+A then F9 in Word to update the table of contents

## Key file paths
- MiniCheck SQL: `/Users/I321356/Documents/claude_project/HANA_Configuration_MiniChecks.txt`
- TPO template: `/Users/I321356/Documents/claude_project/TPO_template.docx`
- Report generator: `/Users/I321356/Documents/claude_project/generate_minicheck_report.py`
- Python venv: `/Users/I321356/Documents/claude_project/sap-hana-mcp/.venv/bin/python`
- Default output: `/Users/I321356/Documents/claude_project/MiniCheck_Report.docx`
