# Changelog

All notable changes to this project are documented here, organized by version.
Dates are in YYYY-MM-DD format (UTC).

---

## v1.4.0 — 2026-04-15

### minicheck-report skill
- **Step 0**: now also deletes `minicheck_results.json` before each run, preventing stale results from a previous system carrying over
- **Step 2**: saves full MiniCheck SQL output to `minicheck_results.json` so the report generator reads CHIDs dynamically at runtime
- **Step 3**: removed obsolete post-processing instructions (cover page, ToC, Action Plan rebuild) — all handled inside `generate_minicheck_report.py`
- **Step 4**: simplified to a verification step checking `[OK]`/`[--]` output lines
- **Step 5 cross-check**: extended to show `PICKED` + `ALT` rows — for each critical CHID, the selected section is marked `PICKED` and every other TPO section whose `Check IDs:` line also references the CHID is listed as `ALT`, enabling manual review of alternate section choices

### generate_minicheck_report.py
- **`build_tpo_index()` rewrite**: CHIDs are now extracted exclusively from the `Check IDs:` line in each TPO H2 section body, not from free-form body text — fixes incorrect matches (e.g. M0420 previously matched "Large Technical Tables" via body prose; now correctly matches "Memory Bottlenecks" via its `Check IDs:` line)
- Entire script is now fully dynamic: no hardcoded CHID lists anywhere; reads critical CHIDs from `minicheck_results.json` at runtime

### .gitignore
- Added `minicheck_report.log` and `minicheck_results.json` — local run artifacts, not tracked in git

---

## v1.3.0 — 2026-04-12

### minicheck-report skill
- **Dynamic TPO section indexing**: replaced hardcoded `CRITICAL_SECTIONS` list with `build_tpo_index()` that scans every H2 section in the TPO template for `Mxxxx` patterns at runtime — ensures all CHIDs are matched regardless of system or HANA version
- **`resolve_sections_for_critical_chids()`**: maps each critical CHID to its best TPO section; deduplicates shared sections while preserving CHID order
- Critical CHIDs sourced from `minicheck_results.json` (written by skill) or CLI argument; script exits with error if neither is available
- Removed `FALLBACK_ACTION_PLAN` hardcoded dict; placeholder sections added automatically for CHIDs with no TPO match

### hana-report-update skill
- Synced documentation with latest script behavior

---

## v1.2.0 — 2026-04-10

### hana-report-update skill
- **Step 0**: added cleanup of previous output files before each run
- **Output naming**: default output now uses `_updated` suffix; added `--overwrite` flag support
- **SQL file selection**: excluded `_MDC` SQL files for tenant DB connections
- Updated README to reference `SQLStatements/` folder instead of the old single `HANA_Configuration_MiniChecks.txt` file

---

## v1.1.0 — 2026-04-09

### minicheck-report skill
- **Cross-check log**: execution log cross-check section now renders as an ASCII table with columns: Status | CHID | MiniCheck Description | TPO Section Title | Priority | TPO Check IDs
- TPO check IDs extracted by scanning section body text in `TPO_template.docx`

### hana-report-update skill
- Added cover page field guidance (system ID, date, author)
- Fixed SQL file mapping table with `next_anchor` hints and workload parameter details
- Added `do_replace()` helper documentation and pitfall notes

### generate_minicheck_report.py
- Action Plan table rebuilt from the full 677-row TPO template table
- Fallback rows constructed for sections missing from the template's Action Plan
- Issue and Recommendation columns enforced to left alignment

---

## v1.0.0 — 2026-04-08

### minicheck-report skill
- **Step 1**: auto-detects HANA version and selects the matching MiniCheck SQL file from `SQLStatements/` (highest version ≤ actual system version; excludes `_Internal_`, `_SSS`, `_ESS` variants)
- **Step 5**: new detailed execution log (`minicheck_report.log`) with sections: System Info, Execution Summary, Critical Findings, TPO cross-check table, Action Plan cross-check, Issues/Warnings
- **Step 6**: final report now includes log file path
- TPO template updated

---

## v0.3.0 — 2026-04-07

### hana-report-update skill
- New skill: automates filling SAP HANA MiniCheck report `.docx` files
- Replaces cyan placeholder text with real SQL query results from HANA
- Fixes table formatting and updates system ID fields
- Full skill documentation in `.claude/skills/hana-report-update/SKILL.md`

### SQLStatements folder
- Added 835 SQL statement files from SAP Note 1969700
- Updated `.gitignore` to unignore the folder

### README
- Added `hana-report-update` skill documentation and usage instructions

---

## v0.2.0 — 2026-04-06

### Core infrastructure
- **`sap-hana-mcp/server.py`**: MCP server supporting 6 HANA tools for both cloud and on-prem connections; reads connection details from environment variables (`HANA_HOST`, `HANA_PORT`, `HANA_USER`, `HANA_PASSWORD`, `HANA_TYPE`)
- **`generate_minicheck_report.py`**: generates TPO-format Word report from MiniCheck findings using `python-docx`; copies sections verbatim from TPO template preserving XML formatting
- **`TPO_template.docx`**: TPO report template with cover page, ToC, Service Summary, Action Plan, General Overview, Check Lists, and Issues & Recommendations sections
- **`.claude/skills/minicheck-report/SKILL.md`**: Claude Code `/minicheck-report` skill definition
- **`README.md`**: project setup and usage instructions
- **`.gitignore`**: initial ignore rules for venv, generated outputs, macOS files

---

## v0.1.0 — 2026-04-05

### Initial commits
- `hello_world.cpp`: initial C++ hello world function (removed in v0.2.0)
- `sap_fiori_dashboard.html`: SAP Fiori dashboard prototype (removed in v0.2.0)
