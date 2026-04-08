---
name: minicheck-report
description: Run SAP HANA MiniCheck against the on-prem system and generate a TPO-format Word report with findings and recommendations
argument-hint: [output-filename.docx]
---

Run a SAP HANA MiniCheck analysis against the on-prem HANA system and generate a Word report in TPO format.

## Steps

### 1. Execute the MiniCheck
First, determine the HANA version of the on-prem system by running:
```sql
SELECT VERSION FROM SYS.M_DATABASE
```

Then select the appropriate MiniCheck SQL file from `/Users/I321356/Documents/claude_project/SQLStatements/` by matching the version suffix in the filename (e.g. `HANA_Configuration_MiniChecks_2.00.073+.txt` for version 2.00.07x). Choose the file with the highest version that is still less than or equal to the actual system version. Do not use the `_Internal_` or `_SSS` or `_ESS` variants.

Run the selected MiniCheck SQL file against the on-prem HANA system:
- Tool: `mcp__sap-hana-onprem__execute_sql_file`
- File path: the selected file from `/Users/I321356/Documents/claude_project/SQLStatements/`

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

### 5. Write execution log
Append a detailed log entry to `/Users/I321356/Documents/claude_project/minicheck_report.log`.
Create the file if it does not exist. Use the Bash tool to append the log entry.

The log entry must contain the following sections:

```
================================================================================
MiniCheck Run: <YYYY-MM-DD HH:MM:SS UTC>
================================================================================
SYSTEM INFO
  System ID     : <SID> / <DB name>
  HANA Version  : <version>
  MiniCheck file: <selected SQL filename>
  Analysis date : <date from M0010 row in results>

EXECUTION SUMMARY
  Total checks  : <N>
  Critical (C=X): <N>
  Output report : <output_path>

CRITICAL FINDINGS (C=X)
  <for each critical finding, one line per item:>
  <CHID>  <VALUE> / <EXPECTED_VALUE>  <DESCRIPTION>  [SAP Note <SAP_NOTE>]

  Example:
  M0115   2304 / <= 600               Service startup time variation (s)              [SAP Note 2177064]
  M0910   8.50 / <= 1.20              Age of last data backup (days)                  [SAP Note 1642148]

CROSS-CHECK: MiniCheck C=X vs. TPO Template Sections
  For each critical CHID, indicate whether a matching Issues & Recommendations
  section was found in the generated report (from generate_minicheck_report.py output):
  [FOUND]   <CHID>  <section title in report>
  [MISSING] <CHID>  <description> — no matching section in template

CROSS-CHECK: MiniCheck C=X vs. Action Plan Table
  For each critical CHID, indicate whether a matching row exists in the
  Action Plan table of the generated report after post-processing:
  [FOUND]   <CHID>  row #<N>  "<Issue text in Action Plan>"
  [MISSING] <CHID>  <description> — no matching row in Action Plan table

ISSUES / WARNINGS
  List any discrepancies found during cross-checks, e.g.:
  - CHIDs present in MiniCheck C=X but missing from both template sections and Action Plan
  - CHIDs where section was added to report but no Action Plan row exists
  - Any other anomalies noticed during post-processing
  If none: "None"
================================================================================
```

### 6. Report results
Tell the user:
- Total checks run
- Number of critical findings (C=X)
- Summary table of all critical findings
- Path to the generated Word report
- Path to the execution log
- Reminder to press Ctrl+A then F9 in Word to update the table of contents

## Key file paths
- MiniCheck SQL files: `/Users/I321356/Documents/claude_project/SQLStatements/HANA_Configuration_MiniChecks_<version>+.txt`
- TPO template: `/Users/I321356/Documents/claude_project/TPO_template.docx`
- Report generator: `/Users/I321356/Documents/claude_project/generate_minicheck_report.py`
- Python venv: `/Users/I321356/Documents/claude_project/sap-hana-mcp/.venv/bin/python`
- Default output: `/Users/I321356/Documents/claude_project/MiniCheck_Report.docx`
- Execution log: `/Users/I321356/Documents/claude_project/minicheck_report.log`
