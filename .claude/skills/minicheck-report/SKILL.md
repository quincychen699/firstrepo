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
- `/Users/I321356/Documents/claude_project/minicheck_results.json` (previous run's cached results)

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

**Save the full MiniCheck results to `minicheck_results.json`** in the project directory so the report generator can read them:

```python
import json, os
results = [...]  # all rows from the MiniCheck SQL output as list of dicts with keys: CHID, C, DESCRIPTION, VALUE, EXPECTED_VALUE, SAP_NOTE, etc.
with open('/Users/I321356/Documents/claude_project/minicheck_results.json', 'w') as f:
    json.dump(results, f, indent=2)
```

Each row dict must contain at minimum: `CHID`, `C`, `DESCRIPTION`, `VALUE`, `EXPECTED_VALUE`, `SAP_NOTE`.

### 3. Generate the Word report
Determine the output filename:
- If `$ARGUMENTS` is provided, use it as the output filename (resolve relative to `/Users/I321356/Documents/claude_project/` if not absolute)
- Otherwise default to `/Users/I321356/Documents/claude_project/MiniCheck_Report.docx`

Run the report generator (it reads critical CHIDs from `minicheck_results.json` automatically):
```
/Users/I321356/Documents/claude_project/sap-hana-mcp/.venv/bin/python \
  /Users/I321356/Documents/claude_project/generate_minicheck_report.py \
  <output_path>
```

The script handles everything: TPO template indexing, section selection, cover page, ToC field, Service Summary with Action Plan table, General Overview, Check Lists, and Issues & Recommendations sections. No post-processing is needed.

### 4. Verify the report
Check the script output for any warnings:
- Lines starting with `[--]` indicate a CHID has no matching TPO template section (a placeholder is added)
- Lines starting with `[OK]` confirm sections were found and copied

Report any `[--]` warnings to the user in the final summary.

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

  - Status    : PICKED (the section used in the report), ALT (alternate section also containing this CHID), or MISS (no match)
  - CHID      : MiniCheck check ID — shown only on the PICKED row; blank on ALT rows
  - MiniCheck Description: description text — shown only on the PICKED row; blank on ALT rows
  - P         : Action Plan priority number from the generated report's Action Plan table (2=High, 3=Medium, - if missing) — PICKED row only
  - TPO Section Title: exact H2 heading from the TPO template; if multiple CHIDs map to the same section,
                       note the shared CHID in parentheses e.g. "(= M0551)"
  - Priority  : priority label read from the TPO template section body (High / Medium / -)
  - TPO Check IDs: check IDs (Mxxxx pattern) listed on the "Check IDs:" line of that TPO template section

  For each CHID, print one PICKED row (the section selected for the report) followed by one ALT row per
  additional section that also lists the CHID in its "Check IDs:" line. This allows manual review of
  alternate sections that could be used instead.

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
