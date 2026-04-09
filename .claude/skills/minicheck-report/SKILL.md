---
name: minicheck-report
description: Run SAP HANA MiniCheck against the on-prem system and generate a TPO-format Word report with findings and recommendations
argument-hint: [output-filename.docx]
---

Run a SAP HANA MiniCheck analysis against the on-prem HANA system and generate a Word report in TPO format.

## Steps

### 0. Clean up existing output files
Before doing anything else, determine the output path (same logic as step 3: use `$ARGUMENTS` if provided, otherwise `/Users/I321356/Documents/claude_project/MiniCheck_Report.docx`).

Then remove any pre-existing files that could conflict or be confused with the new output:
- The output file itself (e.g. `MiniCheck_Report.docx`)
- Any backup copies with the same base name (e.g. `MiniCheck_Report*.docx`, `MiniCheck_Report*.docx.bak`, `MiniCheck_Report_*.docx`)
- The Word auto-recovery / lock file (e.g. `~$MiniCheck_Report.docx`)

Use the Bash tool with `rm -f` to delete them. Print the list of files removed (or "No existing files found" if none).

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
The Action Plan table in the generated report is already built correctly by
`generate_minicheck_report.py` — it contains only the rows matching critical
findings, with columns populated as follows:

- **ID**: sequential number starting from 1
- **DB**: actual system SID (e.g. `HAN`), replacing the `-` placeholder from the template
- **P**: priority value copied verbatim from the matching row in the TPO template's Action Plan table
- **S**: status copied verbatim from the template (typically `O`)
- **Issue**: issue title copied verbatim from the matching template row, matching the section heading in "Issues and Recommendations"
- **Recommendation**: recommendation text copied verbatim from the matching template row

For issues that have a Heading 2 section in the template but no row in the template's Action Plan table (e.g. "Short Backup Retention Period"), a fallback row is constructed using the recommendation text from the section body and priority from the section header.

All data rows in the Issue and Recommendation columns use **left alignment**, consistent with the TPO template.

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
  Format as an ASCII table with columns:
    Status | CHID | MiniCheck Description | P | TPO Section Title | Priority | TPO Check IDs

  - Status    : FOUND (matching H2 section exists in template) or MISS (no match)
  - CHID      : MiniCheck check ID
  - MiniCheck Description: description text from the MiniCheck results row
  - P         : Action Plan priority number from the generated report's Action Plan table (2=High, 3=Medium, - if missing)
  - TPO Section Title: exact H2 heading from the TPO template; if multiple CHIDs map to the same section,
                       note the shared CHID in parentheses e.g. "(= M0551)"
  - Priority  : priority label read from the TPO template section body (High / Medium / -)
  - TPO Check IDs: check IDs (Mxxxx pattern) listed in the body of that TPO template section;
                   extract these by scanning the section text in TPO_template.docx

  Add a footer line: "N unique TPO sections cover all N critical CHIDs (N CHIDs share a section with a related finding)"
  And: "N CHIDs with no TPO section: <list>"

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
