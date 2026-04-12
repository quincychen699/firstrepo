---
name: hana-report-update
description: This skill should be used when the user asks to update, fill in, or process a SAP HANA MiniCheck report (.docx), replace cyan placeholders with real SQL data, fix table formatting, or update system ID fields in the report. Input and output filenames are passed as $ARGUMENTS.
version: 2.0.0
---

# SAP HANA MiniCheck Report Update

This skill covers how to process and update a SAP HANA MiniCheck report `.docx` file by replacing template placeholders with real data from the HANA system.

**Arguments**: `$ARGUMENTS` contains the input filename, optional output filename, and optional `--overwrite` flag, e.g.:
- `/hana-report-update HAN_report.docx` → output is `HAN_report_updated.docx` (default)
- `/hana-report-update HAN_report.docx HAN_report_v2.docx` → explicit output filename
- `/hana-report-update HAN_report.docx --overwrite` → output overwrites the input file

Parse at the top of the script:
```python
import os, shutil, glob
raw_args = "$ARGUMENTS".split()
OVERWRITE = '--overwrite' in raw_args
args = [a for a in raw_args if a != '--overwrite']

INPUT = args[0] if len(args) >= 1 else 'report.docx'

if OVERWRITE:
    OUTPUT = INPUT
elif len(args) >= 2:
    OUTPUT = args[1]
else:
    base, ext = os.path.splitext(INPUT)
    OUTPUT = base + '_updated' + ext   # e.g. HAN_report_updated.docx

# Clean up any previous output files (skip in overwrite mode to protect the input)
if not OVERWRITE:
    out_base = os.path.splitext(OUTPUT)[0]
    for f in glob.glob(out_base + '*'):
        os.remove(f)
        print(f'Removed previous file: {f}')

shutil.copy(INPUT, INPUT + '.bak')  # always back up the input
```
Use `INPUT` to load the document and `OUTPUT` to save the result.

## Overview

The report is a `.docx` file (ZIP archive). All content lives in `word/document.xml`. Paragraphs are split with `re.split(r'(?=<w:p[ >])', body)`. Tables are embedded within paragraph nodes.

## Key Technical Concepts

- **Cyan highlight detection**: `'cyan' in para_xml` identifies unreplaced sample data
- **Contiguous cyan block scanning**: scan forward with `max_gap=5` tolerance to find block boundaries
- **Reverse-order replacement**: apply replacements from highest to lowest index to preserve validity
- **A4 page width math**: usable = 9099 twips; `Courier New` char width at sz=14 (7pt) ≈ 84 twips → **108 chars max**; at sz=16 (8pt) ≈ 96 twips → **94 chars max**. **Every line must stay within these limits — no wrapping allowed.**
- **Font for SQL output**: `Courier New` — equal-width characters ensure column alignment.
- **Font size convention**: `w:val` is in half-points. **Never remove columns for width — always reduce font size first.** Only trim columns as a last resort if even sz=10 (5pt) cannot fit (>151 chars).
  - `sz=16` (8pt): max 94 chars/line
  - `sz=14` (7pt): max 108 chars/line
  - `sz=12` (6pt): max 126 chars/line
  - `sz=10` (5pt): max 151 chars/line
- **`make_para` pattern**:
```python
def make_para(text, sz=14):
    # sz is w:val (half-points): 14=7pt, 16=8pt
    txt = xml_esc(text)
    space = ' xml:space="preserve"' if text.startswith(' ') or '  ' in text else ''
    return (f'<w:p><w:pPr><w:jc w:val="left"/></w:pPr><w:r>'
            f'<w:rPr>'
            f'<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>'
            f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
            f'</w:rPr>'
            f'<w:t{space}>{txt}</w:t></w:r></w:p>')
```
- **Split `<w:t>` nodes**: text spread across multiple nodes requires consolidation before replacement
- **MCP tool**: `mcp__sap-hana-onprem__execute_sql_file` for live HANA queries
- **SQL statements folder**: `SQLStatements/` — 835 SAP Note 1969700 SQL files. **Always use this folder as the SQL source. Never write SQL from scratch.** Search for the right file by topic, pick the highest version ≤ system revision, then pass it to `mcp__sap-hana-onprem__execute_sql_file`.

## SQL File Selection Rules

### How to find the right file
1. `ls SQLStatements/ | grep -i <keyword>` — e.g. `grep -i startup`, `grep -i timezone`, `grep -i backup`
2. **Exclude all files whose name ends in `_MDC` or contains `_MDC_`** — those are for System DB context only and will fail on a tenant DB with `invalid schema name: SYS_DATABASES`
3. From the remaining matches, pick the file whose version suffix is the **highest that is ≤ the system revision**
4. Read the file header (`[NAME]`, `[DESCRIPTION]`, `[VALID FOR]`) to confirm it covers what you need
5. Execute with `mcp__sap-hana-onprem__execute_sql_file` using the full path

### Version selection — detect dynamically each run

**Step 0 (always first)**: query the live system revision before selecting any SQL file:
```sql
SELECT VALUE FROM M_SYSTEM_OVERVIEW WHERE NAME = 'Version'
```
or read it from the document's already-filled `HANA_Configuration_Overview` block (e.g. `|Revision |2.00.059.20...`).

Use the detected revision (e.g. `2.00.059`) to apply the rule:
- ✓ Use any file whose version suffix is **≤ detected revision** (e.g. `2.00.040+`, `2.00.030+`, `2.00.000+`, no-suffix)
- ✗ **Never use `_MDC` files** — they target System DB context and will fail on a tenant DB (`invalid schema name: SYS_DATABASES`)
- ✗ Skip files whose version suffix is **> detected revision** (e.g. if revision is 2.00.059, skip `2.00.060+` and above)
- When multiple valid versions exist, always pick the **highest** that still qualifies
- Never assume the version — always detect it fresh for each new document/system

## Document Structure and SQL File Mapping

### How to approach a new document

**Always process ALL sections in every run — section 3 (General Overview, Workload, Space, Memory, Special Features, Check Lists) AND section 5 (Issues & Recommendations). Never skip section 3.**

1. **Read the document headings** to identify all sections present (some documents have extra sections not in others)
2. **For each cyan block**, read the surrounding text to find which SQL name is referenced (e.g. `SQL: "HANA_Workload"` or `SQL: "HANA_Configuration_MiniChecks"`)
3. **Search SQLStatements/** for the matching file: `ls SQLStatements/ | grep -i <keyword>`
4. **Pick the highest version ≤ system revision** (see rules below)
5. **Execute** with `mcp__sap-hana-onprem__execute_sql_file`
6. **Only replace** cyan blocks where real SQL data is available; leave others untouched
   - **Full output**: always insert the **complete** SQL result set — all rows, not just `C=X` critical ones
   - If the surrounding template text says "only potentially critical issues", replace that label with "System DB:" when inserting the full output
   - Remove any stale template header/separator rows that sit above the new block after replacement
7. **Normalise font and size** on all replaced SQL output paragraphs so characters align and **no line wraps**:
   - **Font**: always `Courier New` — equal-width characters ensure column alignment
   - **Page width limit**: A4 usable width = 9099 twips; at `w:val="14"` (7pt) each char ≈ 84 twips → max **108 chars**; at `w:val="16"` (8pt) each char ≈ 96 twips → max **94 chars**
   - **Size selection**: measure `max_len = max(len(line) for line in block_lines)`
     - `max_len ≤ 94` → use `sz=16` (8pt) — more readable
     - `94 < max_len ≤ 108` → use `sz=14` (7pt) — fits without wrapping
     - `108 < max_len ≤ 126` → use `sz=12` (6pt)
     - `126 < max_len ≤ 151` → use `sz=10` (5pt)
     - `max_len > 151` → **must trim columns** as last resort; add a `-- (column X removed for width)` comment line after the header separator
   - **Never remove columns just because the table is wide — adjust font size first.** Only trim columns if even sz=10 (5pt) cannot fit (>151 chars).
   - Apply `make_para(line, sz)` for every line in the block — including header, separator, data rows, and footer
   - Never mix font sizes within the same SQL output block
   - **Verify before inserting**: check `max(len(l) for l in lines)` — if any line exceeds 151 chars, trim columns as a last resort
8. **Fill in system identity fields** — replace all template placeholder values with the real system values throughout the entire document:
   - `SAP System ID` / `SAP SID` → real SID (e.g. `HAN`)
   - `DB System ID` / `Database System ID` → real SID
   - `Database: …` fields (repeated in every section header) → `Database: <SID>`
   - `DB Version` / `Database Version` → full version string (e.g. `2.00.059.20`)
   - `Operating System` / `OS` placeholder → full OS string (e.g. `SUSE Linux Enterprise Server 12 SP5`)
   - Do this as a **first pass** before any cyan block replacement, so the correct SID appears in all section headers from the start
   - Use targeted `str.replace()` or `re.sub()` on the raw XML — do NOT rely on paragraph-level scanning for these, as the values are often split across multiple `<w:t>` nodes; consolidate runs first if needed
   - **`Database: …` split-run pattern**: `Database:` and ` …` are in separate `<w:r>` runs. Use a cross-run regex, substituting the detected SID:
     ```python
     # SID = detected system ID, e.g. 'HAN'
     data = re.sub(
         r'(<w:t>Database:</w:t></w:r><w:r>(?:<w:rPr>.*?</w:rPr>)?<w:t[^>]*>) …(</w:t>)',
         rf'\g<1> {SID}\2', data, flags=re.DOTALL)
     ```
   - **Cover page fields** (`SAP System ID`, `DB Type`, `DB System ID`, `Database Name`, `Operating System`): these are in `FPItemNotBold` floating-frame paragraphs containing only `…`. Use `update_cover_field()` (see pitfall #6) targeted by `w14:paraId`. Find the correct paraIds by scanning for `FPItemNotBold` + `cyan` paragraphs and matching to surrounding label paragraphs. Apply to `doc_xml_work` before splitting into the paragraph array.

### Full SQL File Mapping (version-agnostic)

Always apply the dynamic version selection rule above when choosing the file. The table below lists the correct file pattern — substitute the highest valid version for the actual system.

**IMPORTANT — Column layout rule**: The output you insert **must match the template's column layout exactly** — same column names (not abbreviations), same column order, same set of columns. Before inserting any block, compare your header row against the template's cyan sample header row. If they differ, either re-run the SQL with different parameters (e.g. different `AGGREGATE_BY`), or post-process the result to select/reorder/rename columns to match.

| Report Section | SQL File to Use | Expected header row (from template) | Notes |
|---|---|---|---|
| SAP HANA Overview (General Info) | `HANA_Configuration_Overview_2.00.040+.txt` | `\|NAME\|VALUE\|SAP_NOTE\|` (key-value format, not a tabular header) | Use `next_anchor='This following overview contains general information'` |
| Infrastructure Report (section 3.2.1) | `HANA_Configuration_Infrastructure_2.00.040+.txt` | key-value format, no column header row | Appears immediately after `HANA_Configuration_Overview` |
| SAP HANA Workload (per day) | `HANA_Workload.txt` | `\|SNAPSHOT_TIME\|EXEC_PER_S\|PREP_PER_S\|TRANS_PER_S\|UPD_TRANS_PER_S\|COMMIT_PER_S\|ROLLBACK_PER_S\|` | Use full column names from SQL output — do not abbreviate. Use `next_anchor='historic SAP HANA load information is'` |
| SAP HANA Load History (per day) | `HANA_LoadHistory_Services_2.00.030+.txt` (DAY) | `\|SNAPSHOT_TIME\|PING_MS\|CPU\|SYS\|USED_GB\|CONNS\|TRANS\|STMT_PS\|ACT_THR\|WAIT_THR\|ACT_SQL\|WAIT_SQL\|PEND_SESS\|...` | Execute as-is (default `TIME_AGGREGATE_BY = 'DAY'`). Use full column names from SQL output. Use `next_anchor='SAP HANA load history: (per hour for recent working day)'` |
| SAP HANA Load History (per hour) | `HANA_LoadHistory_Services_2.00.030+.txt` (HOUR) | `\|SNAPSHOT_TIME\|PING_MS\|CPU\|SYS\|USED_GB\|CONNS\|TRANS\|STMT_PS\|ACT_THR\|WAIT_THR\|ACT_SQL\|WAIT_SQL\|PEND_SESS\|VERSIONS\|COM_RANGE\|HANDLES\|MERGES\|UNLOADS\|` | Copy to `/tmp/hana_loadhistory_hour.txt`, change `'DAY' TIME_AGGREGATE_BY` → `'HOUR' TIME_AGGREGATE_BY`, execute the temp file. **Same 18 columns as per-day** (not EXEC_PER_S etc.). Do not remove columns — use `sz=10` (5pt) if needed. |
| SAP HANA Thread Samples (aggregated) | `HANA_Threads_ThreadSamples_FilterAndAggregation_2.00.040+.txt` | `\|SAMPLES\|PCT\|THREAD_STATE\|Q\|LOCK_NAME\|` | Must copy to temp file, set `'THREAD_STATE' AGGREGATE_BY`. Output column order must be `SAMPLES\|PCT\|THREAD_STATE\|Q\|LOCK_NAME` — reorder if SQL returns them differently. Use `next_anchor='SAP HANA Workload Management Settings'` |
| Workload Management Settings – Parameters | `HANA_Configuration_Parameters_Values_2.00.040+.txt` | `\|FILE_NAME\|SECTION\|PARAMETER_NAME\|LAYER_NAME\|VALUE\|` | Column name is **`LAYER_NAME`**, not `LAYER`. Column widths ≤108: FILE_NAME(15)\|SECTION(23)\|PARAMETER_NAME(37)\|LAYER_NAME(10)\|VALUE(20) |
| Workload Management Settings – Classes | `HANA_Workload_WorkloadClasses_2.00.040+.txt` | (varies — show all result columns) | Empty result → insert `'No workload classes configured (output: empty).'` |
| Space – Largest Tables | `HANA_Tables_LargestTables_2.00.040+.txt` | `\|TABLE_NAME\|S\|L\|T\|U\|P\|COLS\|RECORDS\|DISK_GB\|MEM_GB\|SHAR_GB\|HEAP_GB\|PERS_GB\|PARTS\|TAB_MEM_GB\|INDEX...\|` | Do **not** prepend SCHEMA column or change column names. Use SQL output column names as-is |
| Space – Table Classes | `HANA_Tables_TableClasses.txt` | (key-value format) | Table class distribution |
| Space – Partitioning Overview | `HANA_Tables_ColumnStore_PartitionedTables_2.00.000+.txt` | (varies — show all result columns) | Partitioned tables |
| Memory Overview | `HANA_Memory_Overview_2.00.040+.txt` | `\|NAME\|TOTAL_GB\|DETAIL_GB\|DETAIL2_GB\|` | Physical/HANA/global alloc memory |
| Audit Policies | `HANA_Security_AuditPolicies_1.00.80+.txt` | (key-value format matching `HANA_Configuration_Overview`) | Configured audit policies |
| System Replication | `HANA_Replication_SystemReplication_Overview_1.00.120+.txt` | (varies) | Replication state, lag, backlog |
| Triggers | `HANA_Configuration_Triggers.txt` | `\|SCENARIO\|COUNT\|` | Configured triggers by scenario |
| SAP HANA Mini Checks | highest `HANA_Configuration_MiniChecks_<version>.txt` ≤ revision | `\|CHID\|DESCRIPTION\|VALUE\|EXPECTED_VALUE\|C\|SAP_NOTE\|` | Full mini check suite |
| SAP HANA Trace File Mini Checks | `HANA_TraceFiles_MiniChecks.txt` | (check header row in template) | Trace file error patterns |
| SAP HANA Call Stack Mini Checks | `HANA_Threads_Callstacks_MiniChecks_2.00.040+.txt` | (check header row in template) | Call stack anomaly checks |
| Runtime Tests | `HANA_Tests_Results.txt` | `\|CHID\|DESCRIPTION\|EXECUTIONS\|VALUE\|EXPECTED_VALUE\|C\|TEST_COMMAND\|` | Drop `TEST_COMMAND` column if width >108 chars |
| M0115 – Service Startup Times | `HANA_Startup_StartupTimes.txt` | `\|PORT\|PORT_STARTUP_TIME\|PORT_STARTUP_DELAY_S\|` | Template has exactly **3 columns** — `PORT`, `PORT_STARTUP_TIME`, `PORT_STARTUP_DELAY_S`. Do **not** add `SERVICE_NAME` or any other column. SQL returns PORT-level rows — do not aggregate to HOST level |
| M0209/M0228 – Outdated Linux Kernel | `HANA_Configuration_Infrastructure_2.00.040+.txt` | `\|HOST\|CPU_DETAILS\|CPU_MHZ\|PHYS_MEM_GB\|SWAP_GB\|OP_SYS\|KERNEL_VERSION\|` | Extract only the HOST/KERNEL columns from the infra SQL result. Do not insert the full overview block |
| M0418 – Host Memory Overallocation | `HANA_Memory_Overview_2.00.040+.txt` | `\|HOST\|HOST_TOTAL_GB\|HANA_LIMIT_GB\|HOST_USED_GB\|HANA_ALLOC_GB\|HANA_USED_GB\|USED_DISK_GB\|DISK_PCT\|` | Extract HOST/MEMORY columns from Memory Overview SQL. Do not insert the full overview block |
| M0471 – IPMM Memory | `HANA_Memory_Overview_2.00.040+.txt` | `\|PHYS_TOTAL_GB\|PHYS_USED_GB\|PHYS_USED_PCT\|ALLOC_LIM_GB\|HANA_ALLOC_GB\|HANA_USED_GB\|HANA_USED_PCT\|` | Extract PHYS_*/ALLOC_LIM/HANA_* memory columns. Do not insert the full overview block |
| M0551/M0552 – Timezone Configuration | `HANA_Configuration_Timezones_2.00.040+.txt` | `\|AREA\|KEY\|VALUE\|` | Use full column widths as returned by SQL. Do not truncate the KEY column |
| M0744 – SQL Cache Stats Server | `HANA_SQL_SQLCache_2.00.053+.txt` | `\|SIZE_GB\|SIZE_PCT\|CUM_GB\|CUM_PCT\|PIN_GB\|NUM_SQL\|AVG_PREP_MS\|KB_PER_SQL\|AGGREGATION_CATEGORY\|` | Must filter/aggregate **by schema/category** (not by USER). Set `AGGREGATION_BY = 'SCHEMA_NAME'` in the SQL temp file before executing |
| M0750/M0752/M0753/M0754 – Data Retention | `HANA_StatisticsServer_Histories_RetentionTime_2.00.040+.txt` | `\|ID\|TABLE_NAME\|STATUS\|DEF_RET_DAYS\|CUR_RET_DAYS\|OLDEST_DATA_DAYS\|SIZE_MB\|RETENTION_ALERT\|` | Use full column names — do **not** abbreviate to `DEF\|CUR\|OLDEST\|MB` |
| M0766 – No Workload Class | `HANA_Workload_WorkloadClasses_2.00.040+.txt` | (empty result expected if no classes configured) | Use the same Workload Classes SQL, not Tables or any other SQL |
| M0910 – No recent Data Backup | `HANA_Backups_BackupRuns.txt` | `\|START_TIME\|BACKUP_TYPE\|DATA_TYPE\|RUNTIME_MIN\|BACKUP_SIZE_GB\|MB_PER_S\|DAYS_PASSED\|MESSAGE\|` | Use full column names — do **not** abbreviate (`RUNTIME` not `RUNTIME_MIN`, `SIZE_MB` not `BACKUP_SIZE_GB`, etc.) |
| M0942/M0945 – Short Backup Retention | `HANA_Backups_BackupRuns.txt` | `\|START_TIME\|BACKUP_ID\|BACKUP_TYPE\|STATUS\|BACKUP_SIZE_MB\|DAYS_PASSED\|` | Different columns from M0910 even though same SQL file. Filter or format to show these columns |
| M1142 – SQL Cache Specific Tables | `HANA_SQL_SQLCache_2.00.053+.txt` | `\|SIZE_GB\|SIZE_PCT\|NUM_SQL\|AVG_PREP_MS\|KB_PER_SQL\|STATEMENT_HASH_1\|` | Different aggregation from M0744. Set `AGGREGATION_BY = 'STATEMENT_HASH'` and select top entries |
| M1410/M1415/M1420 – License | `HANA_License_Overview.txt` | `\|TIME_INTERVAL\|LICENSE_LIMIT_GB\|LICENSE_USAGE_GB\|USAGE_PCT\|` | Limit, usage, expiry |
| M2112/M2113/M2115 – Consistency Checks | `HANA_Consistency_CheckTableConsistency_Executions_2.00.040+.txt` | `\|DB_USER\|CHECK_PROCEDURE_NAME\|CHECK_ACTION\|EXECUTIONS\|LAST_START_TIME\|` | Scheduled check runs |
| M2340 – Deprecated Features | `HANA_Features_Usage.txt` | `\|COMPONENT_NAME\|FEATURE_NAME\|DEPRECATED\|CALL_COUNT\|LAST_USAGE_TIME\|USER_NAME\|APP_USER_NAME\|STATE\|` | Use full column names — do **not** abbreviate (`COMPONENT_NAME` not `COMPONENT`, `CALL_COUNT` not `CALLS`, etc.) |
| Statement Hints | `HANA_SQL_PlanStability_StatementHints_2.00.040+.txt` | (varies) | Delivered statement hints status |
| Runtime Checks (section 4.5) | `HANA_Tests_Results.txt` | `\|CHID\|DESCRIPTION\|EXECUTIONS\|VALUE\|EXPECTED_VALUE\|C\|TEST_COMMAND\|` | **Must run prerequisites first** (each 3× via MCP): `HANA_Tests_ArithmeticOperations.txt`, `HANA_Tests_MemoryOperations.txt`, `HANA_Tests_StringOperations.txt` |


### Version Selection Rules
- Always detect the system revision first (see Step 0 above) — do NOT hardcode
- **Never use files with `_MDC` in the name** — these target System DB context and will fail on a tenant DB
- Use any non-MDC file whose version suffix is ≤ detected revision
- Use no-version-suffix files ✓ (valid for all revisions)
- When multiple valid versions exist, always pick the **highest** that still qualifies

## HANA System Info

> **These values change per case — always detect from the live system at the start of each run. Do NOT hardcode.**

Query to detect version and SID:
```sql
SELECT VALUE FROM M_SYSTEM_OVERVIEW WHERE NAME = 'Version'
SELECT VALUE FROM M_SYSTEM_OVERVIEW WHERE NAME = 'Instance ID'
```
Or read from the document's already-filled `HANA_Configuration_Overview` block.

Example values from test_case2.docx (for reference only):
- Version: 2.00.059.20 (SPS05)
- Tenant DB SID: HAN
- Host: hanavirtual
- OS: SUSE Linux Enterprise Server 12 SP5

## Known Pitfalls

### 1. Over-running replacement boundary deletes adjacent blocks
When replacing a cyan block, always determine the **exact end boundary** of that block before replacing. If the boundary is set too wide, paragraphs that follow (e.g. the intro text + cyan block for the *next* SQL section) will be silently deleted.

- **Affected case**: replacing `HANA_Configuration_Overview` (section 3.2.1) deleted the `HANA_Configuration_Infrastructure` intro paragraph (`"This following overview contains general information…"`) that immediately follows.
- **Root cause**: `find_cyan_block(..., max_gap=5)` bridged the one-para gap between the overview's closing `---` line and a cyan "Attention:" note two paras later, extending `last` past the intro text. A subsequent boundary scan using `infra_intro - 3` as the loop ceiling stopped *before* the closing separator, so `last_ov` was never corrected.
- **Correct fix — walk backwards from the next section's anchor**:
  ```python
  # Find the non-cyan intro paragraph that opens the next section
  next_section = find_para(paras, 'This following overview contains general information', first + 1)
  if next_section is None:
      next_section = find_para(paras, 'HANA_Configuration_Infrastructure', first + 1)
  if next_section:
      # Walk backwards to find the true last cyan para of the current block
      for i in range(next_section - 1, first, -1):
          if 'cyan' in paras[i]:
              last = i   # overwrite whatever find_cyan_block returned
              break
  ```
  This is safe regardless of how many non-cyan gaps appear between the two sections.
- **`do_replace` helper — use `next_anchor` parameter**: when the section being replaced is immediately followed by another section with a non-cyan intro line, pass `next_anchor='<that intro text>'` to cap the boundary automatically:
  ```python
  paras, ok = do_replace(paras, 'Load History (per day)',
                          'The historic SAP HANA load information is',
                          day_lines, ...,
                          next_anchor='SAP HANA load history: (per hour for recent working day)')
  ```
  The `do_replace` implementation applies the walk-backwards cap internally:
  ```python
  if next_anchor:
      next_idx = find_para(paras, next_anchor, first + 1)
      if next_idx is not None:
          for i in range(next_idx - 1, first, -1):
              if 'cyan' in paras[i]:
                  last = i
                  break
  ```
- **Known affected section pairs** (both intro lines were lost without this fix):
  - `HANA_Configuration_Overview` → `HANA_Configuration_Infrastructure` intro (`"This following overview contains general information…"`)
  - Workload per-day block → `"SAP HANA workload overview: (per hour for recent working day)"`
  - Load history per-day block → `"SAP HANA load history: (per hour for recent working day)"`
  - Thread samples block → `"SAP HANA Workload Management Settings"` heading (entire 3.3.2 section heading deleted)
- **Verification**: after every replacement, assert `para_text(paras[new_last + 1])` matches the expected opening text of the next section.
- **Recovery — orphaned cyan rows with missing heading**: if a section heading is missing but its cyan data rows are still present (orphaned), do NOT use `do_replace` — it will find the wrong anchor. Instead:
  1. Identify the orphaned cyan block by index (rows with no heading paragraph above them)
  2. Extract the correct heading paragraphs from the `.bak` original document by index
  3. Execute the correct SQL for that section
  4. Delete the orphaned cyan block and insert `heading_paras + sql_output_paras` in one operation:
  ```python
  new_section = list(heading_paras_from_orig)    # non-cyan, preserved from original
  new_section += [make_para(l, sz) for l in sql_lines]
  paras = paras[:orphan_first] + new_section + paras[orphan_last+1:]
  ```
  This is safer than `do_replace` because it avoids any anchor-search ambiguity.

### 2. `Database: …` split-run pattern never matched by simple replace
`Database:` and ` …` are in **separate `<w:r>` runs** in the XML. A plain `str.replace('Database: …', ...)` will never match. Use a cross-run regex (see step 8).

### 3. Never use `_MDC` SQL files — they target System DB, not tenant DB
Files containing `_MDC` in their name (e.g. `HANA_Workload_1.00.90+_MDC.txt`, `HANA_Backups_BackupRuns_1.00.90+_MDC.txt`, `HANA_Replication_SystemReplication_Overview_1.00.120+_MDC.txt`) reference `SYS_DATABASES` which does not exist in a tenant DB context. They will fail with `invalid schema name: SYS_DATABASES`. Always use the non-MDC version of the same SQL file.

### 4. TIME_AGGREGATE_BY defaults to DAY — change to HOUR for hourly blocks
`HANA_LoadHistory_Services_2.00.030+.txt` defaults to `'DAY'`. For hourly output, copy to a temp file and change `'DAY' TIME_AGGREGATE_BY` → `'HOUR' TIME_AGGREGATE_BY` before executing. The per-hour block uses the **same LoadHistory SQL** (not HANA_Workload) and the **same 18 columns** as the per-day block: `SNAPSHOT_TIME|PING_MS|CPU|SYS|USED_GB|CONNS|TRANS|STMT_PS|ACT_THR|WAIT_THR|ACT_SQL|WAIT_SQL|PEND_SESS|VERSIONS|COM_RANGE|HANDLES|MERGES|UNLOADS`. Do **not** remove columns for width — use `sz=10` (5pt) if needed to fit all 18 columns.

### 5. Thread Samples SQL requires AGGREGATE_BY override
`HANA_Threads_ThreadSamples_FilterAndAggregation_2.00.040+.txt` defaults to `'NONE' AGGREGATE_BY`, which returns one row per individual thread sample — not the aggregated thread-state summary the report expects. Running it as-is returns the current query's own row and appears to have no useful data.

**Fix**: copy to a temp file and override the parameter before executing:
```python
import shutil
shutil.copy('SQLStatements/HANA_Threads_ThreadSamples_FilterAndAggregation_2.00.040+.txt',
            '/tmp/hana_threadsamples.txt')
data = open('/tmp/hana_threadsamples.txt').read()
data = data.replace("'NONE' AGGREGATE_BY", "'THREAD_STATE' AGGREGATE_BY", 1)
open('/tmp/hana_threadsamples.txt', 'w').write(data)
# then execute /tmp/hana_threadsamples.txt via MCP
```
This produces one row per `THREAD_STATE` with `SAMPLES` and `PCT` columns — matching the template's expected `|SAMPLES|PCT|THREAD_STATE|Q|LOCK_NAME|` layout.

### 6. Runtime Checks require prerequisite test runs
`HANA_Tests_Results.txt` reads from `M_SQL_PLAN_CACHE_RESET` and returns empty unless the three test SQLs have been executed first (each at least 3×): `HANA_Tests_ArithmeticOperations.txt`, `HANA_Tests_MemoryOperations.txt`, `HANA_Tests_StringOperations.txt`.

### 7. Phase 1 raw XML regex must be applied per-paragraph — never on full doc_xml
**Never** apply the `Database: …` three-run regex (or any DOTALL pattern with `.*?`) on the full `doc_xml` string. With `flags=re.DOTALL`, `.*?` can bridge `</w:p>` paragraph boundaries, matching from a `Database:` in one section across thousands of bytes to an `…` character in a completely different section — silently consuming and deleting all content in between.

**Affected case**: The three-run `Database: …` pattern matched from a `Database:` paragraph across 85,998 bytes to an `…` in a distant section, deleting the `startup times` paragraph and several section 5 headings. This caused `do_replace` to report "anchor not found" for M0115 and M0209 — not because the anchors moved, but because their paragraph content was physically deleted.

**Fix**: Split `doc_xml` into paragraph fragments first, apply each Phase 1 regex only within each paragraph's XML, then rejoin:
```python
_paras_p1 = re.split(r'(?=<w:p[ >])', doc_xml)
_pat2 = re.compile(
    r'(<w:t>Database:</w:t></w:r><w:r>(?:<w:rPr>.*?</w:rPr>)?<w:t[^>]*>) \u2026(</w:t>)',
    re.DOTALL)
_pat3 = re.compile(
    r'(<w:t>Database:</w:t></w:r>)'
    r'<w:r>(?:<w:rPr>.*?</w:rPr>)?<w:t[^>]*> </w:t></w:r>'
    r'(<w:r[^>]*>(?:<w:rPr>.*?</w:rPr>)?<w:t[^>]*>)\u2026(</w:t></w:r>)',
    re.DOTALL)
for _i, _p in enumerate(_paras_p1):
    if 'Database:' not in _p:
        continue
    _new, _n = _pat2.subn(rf'\g<1> {SID}\2', _p)
    if _n == 0 and '\u2026' in _p:
        _new, _n = _pat3.subn(
            rf'\g<1><w:r><w:rPr>...</w:rPr>'
            rf'<w:t xml:space="preserve"> {SID}</w:t></w:r>',
            _p)
    if _n:
        _paras_p1[_i] = _new
doc_xml = ''.join(_paras_p1)
```
This physically prevents cross-boundary matching since each regex call only sees a single paragraph's XML.

### 8. search_start must account for para index drift and TOC conflicts
**Do NOT hardcode `search_start` values** based on original document paragraph positions. Each `do_replace` call changes the total paragraph count — earlier replacements that shrink or expand the array shift all subsequent paragraph indices. A hardcoded `search_start=1750` that was correct for the original document may skip an anchor that drifted to index 1369 after earlier replacements.

**Rule**: Use `search_start=0` for all section 3 anchors and for section 5 anchors that do NOT appear in the Table of Contents.

**TOC conflict**: Some section 5 anchor texts (e.g. "Outdated Linux Kernel Version") appear in **both** the Table of Contents (~paras 447–536 in the original document) **and** the actual section 5 content (~para 4000+). With `search_start=0`, `find_para` returns the TOC copy first, which has no cyan block following it — the replacement is silently skipped with "no cyan block found".

**Fix for TOC-conflicted anchors**: Use `search_start=600` — past the TOC (which ends around para 536) but well before section 5 content. The following section 5 anchors have TOC conflicts and require `search_start=600`:
- Outdated Linux Kernel (M0209/M0228)
- Host Memory Overallocation (M0418)
- IPMM Memory (M0471)
- Timezone Configuration (M0551/M0552)
- SQL Cache Statistics Server (M0744)
- Data Retention (M0750/M0752/M0753/M0754)
- No Workload Class (M0766)
- Short Backup Retention (M0942/M0945)
- SQL Cache Specific Tables (M1142)
- Deprecated Features (M2340)

All other anchors (section 3 blocks, M0115 Startup Times, M0910 Backup, M1410 License, M2112 Consistency Checks) use `search_start=0`.

### 9. SQL output columns must match the template's sample column layout exactly

**Never insert SQL output that uses different column names, a different column order, or a different set of columns than what the template's cyan sample shows.** The template's cyan block is the specification — match it.

Common violations and their root causes:

**Abbreviated column names**: The raw SQL result may return short names like `EXEC/S`, `RLBK/S`, `P_MS`, `CALLS`, `COMPONENT`. The template expects the full names: `EXEC_PER_S`, `ROLLBACK_PER_S`, `PING_MS`, `CALL_COUNT`, `COMPONENT_NAME`. Use the full names as returned by the SQL file's header row.

**Wrong column selection from multi-purpose SQLs**: Several section 5 blocks reuse the same SQL file but expect a *subset* of columns targeted to the issue:
- M0209 (Outdated Kernel): extract `HOST|CPU_DETAILS|CPU_MHZ|PHYS_MEM_GB|SWAP_GB|OP_SYS|KERNEL_VERSION` from infra SQL — not the full overview
- M0418 (Host Memory): extract `HOST|HOST_TOTAL_GB|HANA_LIMIT_GB|HOST_USED_GB|HANA_ALLOC_GB|HANA_USED_GB|USED_DISK_GB|DISK_PCT` from memory SQL
- M0471 (IPMM): extract `PHYS_TOTAL_GB|PHYS_USED_GB|PHYS_USED_PCT|ALLOC_LIM_GB|HANA_ALLOC_GB|HANA_USED_GB|HANA_USED_PCT` from memory SQL
- M0744 (SQL Cache Stats): set `AGGREGATION_BY = 'SCHEMA_NAME'` to get `SIZE_GB|SIZE_PCT|CUM_GB|CUM_PCT|PIN_GB|NUM_SQL|AVG_PREP_MS|KB_PER_SQL|AGGREGATION_CATEGORY`
- M1142 (SQL Cache Tables): set `AGGREGATION_BY = 'STATEMENT_HASH'` to get `SIZE_GB|SIZE_PCT|NUM_SQL|AVG_PREP_MS|KB_PER_SQL|STATEMENT_HASH_1`

**Wrong SQL used for a section**: Some sections reuse SQL with different parameters. The per-hour Load History block uses `HANA_LoadHistory_Services` SQL with `TIME_AGGREGATE_BY = 'HOUR'` — **same SQL as per-day, not HANA_Workload**. The template header for per-hour is identical to per-day: `|SNAPSHOT_TIME|PING_MS|CPU|SYS|USED_GB|CONNS|TRANS|STMT_PS|ACT_THR|WAIT_THR|ACT_SQL|WAIT_SQL|PEND_SESS|VERSIONS|COM_RANGE|HANDLES|MERGES|UNLOADS|`.

**Wrong aggregation for Thread Samples**: Column order must be `SAMPLES|PCT|THREAD_STATE|Q|LOCK_NAME` — the SQL result returns them in a different order; reorder when building the output lines.

**Verification step**: Before inserting, compare the first `|`-row of your formatted output against the cyan sample header in the original template. They must match character-for-character on column names (widths may differ).

### 10. Anchor text must not include curly-quoted SQL namesDocument XML uses Unicode curly quotes (`\u201c`/`\u201d`) for SQL names in anchor strings (e.g. `SQL: \u201cHANA_Workload\u201d`). Anchor strings written with ASCII double quotes will never match.

**Fix**: Avoid including the quoted SQL name in anchor text entirely. Use the surrounding descriptive text instead:
- ✗ `'workload on SAP HANA side (SQL: "HANA_Workload"'` — uses ASCII quotes, won't match
- ✓ `'workload on SAP HANA side (SQL:'` — stops before the opening quote, always matches

### 11. SQL output table separator format — plain `---` lines, no pipe borders

**Every SQL output table in this template uses plain dash lines (no pipe characters) as top and bottom separators.** Do NOT produce `|---+---+---|` pipe-bordered separator rows. The correct format is:

```
------------------------------------------------------------   ← top separator (plain dashes)
|COL_A       |COL_B |COL_C                                |   ← header row
------------------------------------------------------------   ← header/data separator (plain dashes)
|value1      |value2|value3                               |   ← data rows
|value4      |value5|value6                               |
------------------------------------------------------------   ← bottom separator (plain dashes)
```

**Rules**:
- The top separator, the separator between header and data rows, and the bottom separator are all **identical plain dash lines**.
- The separator length must be **exactly equal to the length of the header row** (count the characters in the `|COL1|COL2|...|` line and produce that many dashes).
- The data rows and header row retain their pipe `|` column borders — only the separators between sections are plain dashes.
- **Verification**: `assert len(separator_line) == len(header_row)` before inserting.

Example for a 96-char header row:
```python
header = '|SNAPSHOT_TIME   |EXEC_PER_S|PREP_PER_S|TRANS_PER_S|UPD_TRANS_PER_S|COMMIT_PER_S|ROLLBACK_PER_S|'
sep    = '-' * len(header)   # 96 dashes — matches exactly
```

**Affected sections** where this was incorrectly formatted in past runs:
WORKLOAD (per-day, per-hour), LOADHISTORY (per-day, per-hour), THREAD_SAMPLES, STARTUP, WORKLOAD_PARAMS, LARGEST_TABLES, TABLE_CLASSES, INFRA, MEMORY, IPMM, SQL_CACHE_STATS, RETENTION, BACKUP_DATA, DEPRECATED, CONSISTENCY.

### 12. Cover page fields are floating-frame paragraphs — use paraId for targeting
Cover page system fields (`SAP System ID`, `DB Type`, `DB System ID`, `Database Name`, `Operating System`) use `FPItemNotBold` paragraph style inside `<w:framePr>` floating frames. They cannot be found by text content (all contain only `…`). Target them by `w14:paraId`.

**Known paraIds for the standard MiniCheck template** (these are fixed per template version — verify once if using a different template):

| paraId | Field | Value to insert |
|---|---|---|
| `25074F4E` | SAP System ID | SID (e.g. `HAN`) |
| `346D780F` | DB Type | Full version string — **special case, see below** |
| `1C7A46E5` | DB System ID | SID (e.g. `HAN`) |
| `73BB1639` | Database Name | SID (e.g. `HAN`) |
| `75585514` | Operating System | Full OS string (e.g. `SUSE Linux Enterprise Server 12 SP5`) |

**How to find the correct paraIds** (do once per template version):
```python
paras = re.split(r'(?=<w:p[ >])', doc_xml)
for i, p in enumerate(paras):
    if 'FPItemNotBold' in p and 'cyan' in p:
        pid = re.search(r'w14:paraId="([^"]+)"', p)
        txt = re.sub(r'<[^>]+>', '', p).strip()
        print(f'Para {i} [{pid.group(1) if pid else "no-pid"}]: {repr(txt[:80])}')
```
Identify which paragraph index corresponds to which field from the surrounding label paragraphs (e.g. para 12 = `"SAP System ID"` label → para 13 is the value field).

**DB Type (paraId `346D780F`) — multi-run special case**: This paragraph has its text split across **5 separate `<w:r>` runs**: `SAP HANA` + ` Database ` + `2.` + `00` + `…` (the last run is cyan). A simple cyan-run replacement would only replace `…` leaving `2.00…` → `2.00.059.20` which would be wrong after the dots. Instead, **replace the entire paragraph body** (everything between `<w:pPr>` and `</w:p>`) with a single clean run:
```python
VERSION = '2.00.059.20'  # detected from live system
doc_xml = re.sub(
    r'(w14:paraId="346D780F"[^>]*>.*?<w:pPr>.*?</w:pPr>)'
    r'.*?(</w:p>)',
    lambda m: (
        m.group(1) +
        f'<w:r><w:t>SAP HANA Database {VERSION}</w:t></w:r>' +
        m.group(2)
    ),
    doc_xml, flags=re.DOTALL)
```

**Replacement function for other fields** (in-place, preserves style and frame):
```python
def update_cover_field(xml, para_id, new_value):
    pat = r'(<w:p [^>]*w14:paraId="' + re.escape(para_id) + r'"[^>]*>)(.*?)(</w:p>)'
    m = re.search(pat, xml, re.DOTALL)
    if not m:
        return xml, False
    full_para = m.group(0)
    # Remove cyan from paragraph-level rPr (inside pPr)
    new_para = re.sub(
        r'(<w:pPr>.*?<w:rPr>)(.*?)(</w:rPr>)(.*?</w:pPr>)',
        lambda mm: mm.group(1) + mm.group(2).replace('<w:highlight w:val="cyan"/>', '') + mm.group(3) + mm.group(4),
        full_para, count=1, flags=re.DOTALL)
    # Replace the cyan run's text and remove its highlight
    def replace_cyan_run(m2):
        val = xml_esc(new_value)
        space = ' xml:space="preserve"' if new_value.startswith(' ') or '  ' in new_value else ''
        new_rpr = m2.group(2).replace('<w:highlight w:val="cyan"/>', '')
        return f'{m2.group(1)}<w:rPr>{new_rpr}</w:rPr><w:t{space}>{val}</w:t></w:r>'
    new_para = re.sub(
        r'(<w:r[^>]*>)<w:rPr>(.*?<w:highlight w:val="cyan"/>.*?)</w:rPr>(<w:t[^>]*>)…</w:t></w:r>',
        replace_cyan_run, new_para, count=1, flags=re.DOTALL)
    if new_para == full_para:
        return xml, False
    return xml[:m.start()] + new_para + xml[m.end():], True
```

Apply these substitutions to `doc_xml_work` **before** splitting into the paragraph array.

## What Was Done

### 1. Sections 3–4: Replace cyan placeholders with real SQL data
Executed live SQL queries via MCP tool and replaced all cyan-highlighted sample data blocks with actual results. Covered: performance load overview, thread states, workload classes, blocked transactions, table distribution, memory allocation, disk usage, backup status, license info, and more.

### 2. Section 5: Issues and Recommendations
Replaced all 44 cyan placeholder blocks with real SQL output data:
- Service startup times
- Host/infrastructure overview
- Memory resource utilization
- Timezone configuration
- SQL cache consumers (statistics server + specific tables)
- Data retention times
- Backup runs & catalog
- License limit
- Consistency checks
- Deprecated feature usage

### 3. Table formatting – fit to one line
Resized all SQL output table blocks to `Courier New` font. Size selection: sz=16 (8pt) if max line ≤94 chars, sz=14 (7pt) if 94–108 chars, trim columns if >108 chars.

### 6. Cyan highlight policy
**Only replace cyan blocks where real SQL output data is available.** Do NOT strip or remove cyan highlights from blocks that cannot be filled with actual data (e.g. customer-specific sections, ABAP overview, check lists, or any block where no SQL query was run). Those blocks must remain cyan and unchanged so the customer can identify what still needs to be filled manually.

- Replace cyan: blocks backed by a live SQL query result — insert the **full** result set (all rows)
- Keep cyan: blocks with no corresponding SQL data (customer-specific, ABAP, check list items, etc.)
- When inserting full output, update any template label that says "only potentially critical issues" → "System DB:" and remove stale template header/separator rows above the new block

The global cyan strip step (`re.sub(r'<w:highlight w:val="cyan"/>', '', ...)`) must **NOT** be applied. Only targeted `replace_block()` calls should remove cyan from replaced sections.

### 7. Avoiding malformed XML from strip_courier
The `strip_courier` function can leave empty `</>` tags if `<w:rFonts>` removal leaves a bare closing tag. After applying it, always clean up:
```python
data = data.replace('</>', '').replace('<>', '')
data = re.sub(r'<w:rPr>\s*</w:rPr>', '', data)
```
Verify with `xml.etree.ElementTree.fromstring(data)` before saving.
Removed Courier New font from 45 non-SQL-output paragraphs in section 5, restoring body text style. Key function:
```python
def strip_courier(p):
    result = re.sub(r'<w:rFonts[^/]*/>', '', p)
    result = re.sub(r'<w:rFonts[^>]+>.*?</w:rFonts>', '', result)
    result = re.sub(r'<w:sz w:val="\d+"/>', '', result)
    result = re.sub(r'<w:szCs w:val="\d+"/>', '', result)
    result = re.sub(r'<w:rPr>\s*</w:rPr>', '', result)
    return result
```

### 5. Fill in System ID fields
Replace all template placeholders using values detected from the live system (never hardcode):
- SAP System ID → detected SID
- DB System ID → detected SID
- DB Version → detected full version string
- OS → detected OS string
- All `Database: …` fields → `Database: <SID>`

## Key Helper Functions

```python
def find_cyan_block(paras, start, end=None, max_gap=5):
    """Find contiguous block of cyan paragraphs starting at/after start."""
    if start is None: return None
    # find first cyan para
    first = None
    for i in range(start, end or len(paras)):
        if 'cyan' in paras[i]:
            first = i
            break
    if first is None: return None
    # extend with max_gap tolerance
    last = first
    gap = 0
    for i in range(first+1, end or len(paras)):
        if 'cyan' in paras[i]:
            last = i
            gap = 0
        else:
            gap += 1
            if gap > max_gap:
                break
    return (first, last)

def find_para(paras, text, start=0):
    for i in range(start, len(paras)):
        if text in para_text(paras[i]): return i
    return None

def do_replace(paras, section_label, anchor_text, new_lines, sql_file='', log_obj=None,
               search_start=0, search_end=None, max_gap=5, next_anchor=None, notes=None):
    """Find cyan block near anchor_text and replace with new_lines.

    next_anchor: text of the non-cyan paragraph that opens the *next* section.
    When provided, the cyan block boundary is capped by walking backwards from
    that paragraph — preventing max_gap bridging from swallowing the next
    section's intro line (see pitfall #1).

    notes: list of strings describing parameter changes or column decisions,
    included in the log entry for this replacement.
    """
    idx = find_para(paras, anchor_text, search_start)
    if idx is None:
        print(f'  WARNING: anchor not found: {anchor_text!r}')
        return paras, False
    blk = find_cyan_block(paras, idx, search_end, max_gap)
    if blk is None:
        print(f'  WARNING: no cyan block found after: {anchor_text!r}')
        return paras, False
    first, last = blk
    # Cap boundary at the next section's intro to prevent over-run
    if next_anchor:
        next_idx = find_para(paras, next_anchor, first + 1)
        if next_idx is not None:
            for i in range(next_idx - 1, first, -1):
                if 'cyan' in paras[i]:
                    last = i
                    break
    max_len = max((len(l) for l in new_lines), default=0)
    sz = choose_sz(new_lines)
    # Only trim if even sz=10 (5pt) cannot fit
    trimmed, was_trimmed = trim_to_108(new_lines) if max_len > 151 else (new_lines, False)
    new_paras = [make_para(l, sz) for l in trimmed]
    paras = paras[:first] + new_paras + paras[last + 1:]
    if log_obj:
        log_obj.record(section_label, 'Replaced', sql_file=sql_file, rows=len(new_lines),
                       sz=sz, max_len=max_len, cols_trimmed=was_trimmed,
                       notes=notes or [])
    return paras, True


def choose_sz(lines):
    """Select Courier New w:val size to fit all lines on A4 without wrapping."""
    ml = max((len(l) for l in lines), default=0)
    if ml <= 94:  return 16   # 8pt
    if ml <= 108: return 14   # 7pt
    if ml <= 126: return 12   # 6pt
    return 10                  # 5pt — fits up to ~151 chars

def make_para(text, sz=14):
    """Courier New paragraph at given half-point size (sz=14→7pt, sz=16→8pt)."""
    txt = xml_esc(text)
    space = ' xml:space="preserve"' if text.startswith(' ') or '  ' in text else ''
    return (f'<w:p><w:pPr><w:jc w:val="left"/></w:pPr><w:r>'
            f'<w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>'
            f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
            f'<w:t{space}>{txt}</w:t></w:r></w:p>')
```

## Change Log

Every report update run **must** produce a log file alongside the output document. The log file documents every change made so the consultant can review what was automated vs. what still needs manual attention.

### Log file naming

```python
import os, datetime
LOG = os.path.splitext(OUTPUT)[0] + '_update_log.txt'
```

Example: `HAN_report.docx` → output `HAN_report_updated.docx` → log `HAN_report_updated_update_log.txt`

### ChangeLog helper class

Include this class at the top of every update script, after the imports:

```python
class ChangeLog:
    def __init__(self, path, inp, out, sid, ver, host, os_s):
        self.path = path; self.entries = []; self.skipped = []
        self.start_time = datetime.datetime.now()
        self.meta = {'input':inp,'output':out,'sid':sid,'version':ver,'host':host,'os':os_s}

    def record(self, section, action, detail='', rows=0, sql_file='',
               sz=None, max_len=None, cols_trimmed=False, notes=None):
        """Record a completed replacement with font/width metadata."""
        self.entries.append({
            'section': section, 'action': action, 'detail': detail,
            'rows': rows, 'sql_file': sql_file,
            'sz': sz, 'max_len': max_len, 'cols_trimmed': cols_trimmed,
            'notes': notes or [],
            'time': datetime.datetime.now().strftime('%H:%M:%S'),
        })

    def skip(self, section, reason, heading=None, para_idx=None):
        """Record a block intentionally left cyan, with document location."""
        self.skipped.append({'section': section, 'reason': reason,
                             'heading': heading, 'para_idx': para_idx})

    _SZ_LABEL    = {16: '8pt', 14: '7pt', 12: '6pt', 10: '5pt'}
    _SZ_MAXCHARS = {16: 94,   14: 108,   12: 126,   10: 151}

    # Map section labels to their document group for ordered output
    _SECTION_GROUP = {
        'Section headers':    '1. Cover / Identity',
        'Cover page fields':  '1. Cover / Identity',
        # Section 3 entries map to '2. Section 3 — General Overview'
        # Section 4/MiniCheck entries map to '3. Section 4 — Mini Checks'
        # Section 5 (M-prefixed) entries map to '4. Section 5 — Issues & Recommendations'
    }

    @staticmethod
    def _group(section):
        if section in ('Section headers', 'Cover page fields'):
            return '1. Cover / Identity'
        if re.match(r'M\d', section):
            return '4. Section 5 — Issues & Recommendations'
        if any(k in section for k in ('MiniChecks', 'Callstacks', 'TraceFiles',
                                       'Runtime Tests', 'Security_Mini')):
            return '3. Section 4 — Mini Checks'
        return '2. Section 3 — General Overview'

    @staticmethod
    def _table(rows, col_widths, header=True):
        sep = '+' + '+'.join('-' * (w + 2) for w in col_widths) + '+'
        lines = [sep]
        for i, row in enumerate(rows):
            cells = '|' + '|'.join(f' {str(c):<{w}} ' for c, w in zip(row, col_widths)) + '|'
            lines.append(cells)
            if header and i == 0:
                lines.append(sep)
        lines.append(sep)
        return lines

    def write(self, cb, ca, pb, pa):
        W = 80
        def subhdr(t):
            return ['', f'  {t}', '  ' + '-' * (W - 2)]

        L = ['=' * W, '  SAP HANA MiniCheck Report — Update Log', '=' * W]
        L += [
            f"  Date/Time  : {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"  Input      : {self.meta['input']}",
            f"  Output     : {self.meta['output']}",
            f"  SID        : {self.meta['sid']}",
            f"  Version    : {self.meta['version']}",
            f"  Host       : {self.meta['host']}",
            f"  OS         : {self.meta['os']}",
        ]

        L += subhdr('SUMMARY')
        summary_rows = [
            ('Metric', 'Before', 'After', 'Delta'),
            ('Paragraphs', pb, pa, pa - pb),
            ('Cyan paras', cb, ca, -(cb - ca)),
        ]
        L += self._table(summary_rows, [14, 8, 8, 8])
        L += [
            f"  Replacements made : {len(self.entries)}",
            f"  Blocks left cyan  : {len(self.skipped)}",
        ]

        L += subhdr('REPLACEMENTS MADE  (in document order)')
        seen_groups = []
        grouped = []
        for e in self.entries:
            g = self._group(e['section'])
            if g not in seen_groups:
                seen_groups.append(g)
            grouped.append((g, e))

        for grp in seen_groups:
            entries = [e for g, e in grouped if g == grp]
            L += ['', f'  ┌─ {grp} ─' + '─' * max(0, W - 6 - len(grp))]
            for e in entries:
                L.append(f"  │")
                L.append(f"  ├─ [{e['time']}] {e['section']}")
                info_rows = [('Field', 'Value')]
                info_rows.append(('Action', e['action']))
                if e['sql_file']:
                    info_rows.append(('SQL file', e['sql_file']))
                if e['rows']:
                    info_rows.append(('Rows inserted', str(e['rows'])))
                if e['detail']:
                    detail = e['detail']
                    while len(detail) > 54:
                        split = detail[:54].rfind(' ')
                        if split < 5: split = 54
                        info_rows.append(('Detail' if not any(r[0] == 'Detail' for r in info_rows) else '', detail[:split]))
                        detail = detail[split:].lstrip()
                    info_rows.append(('Detail' if not any(r[0] == 'Detail' for r in info_rows) else '', detail))
                if e['sz'] is not None:
                    sz_label = self._SZ_LABEL.get(e['sz'], f"{e['sz']}hp")
                    max_chars = self._SZ_MAXCHARS.get(e['sz'], '?')
                    info_rows.append(('Font size', f'Courier New {sz_label}  (max {max_chars} chars/line on A4)'))
                if e['max_len'] is not None:
                    thresholds = [(94, '8pt'), (108, '7pt'), (126, '6pt'), (151, '5pt')]
                    exceeded = [f'> {t} chars → {lbl}' for t, lbl in thresholds if e['max_len'] > t]
                    reason = exceeded[-1] if exceeded else '≤ 94 chars → 8pt'
                    info_rows.append(('Line width', f"{e['max_len']} chars  [{reason}]"))
                if e['cols_trimmed']:
                    info_rows.append(('WARNING', 'Lines > 151 chars — some columns truncated'))
                for note in e['notes']:
                    info_rows.append(('Note', note))
                tbl = self._table(info_rows, [14, 54])
                for tline in tbl:
                    L.append('  │    ' + tline)
            L.append(f"  └─ end of {grp}")

        # ── Blocks left cyan — 3-column table with document location ─────────
        L += subhdr('BLOCKS LEFT CYAN  (require manual attention)')
        col_w = [32, 36, 46]
        hdr_sep = '  +' + '+'.join('-' * (w + 2) for w in col_w) + '+'
        def hrow(a, b, c):
            return ('  |' + f' {a:<{col_w[0]}} ' + '|'
                          + f' {b:<{col_w[1]}} ' + '|'
                          + f' {c:<{col_w[2]}} ' + '|')
        row_sep = '  ' + '-' * (sum(col_w) + len(col_w) * 3 + 1)
        L += [hdr_sep, hrow('Section', 'Location (heading / para#)', 'Reason'), hdr_sep]

        def wrap(text, width):
            lines = []
            while len(text) > width:
                split = text[:width].rfind(' ')
                if split < 5: split = width
                lines.append(text[:split])
                text = text[split:].lstrip()
            lines.append(text)
            return lines

        for s in self.skipped:
            section = s['section']
            reason  = s['reason']
            heading = s.get('heading') or ''
            para_idx = s.get('para_idx')
            loc = heading + (f'  (para {para_idx})' if para_idx is not None else '')

            sl = wrap(section, col_w[0])
            ll = wrap(loc,     col_w[1])
            rl = wrap(reason,  col_w[2])
            row_h = max(len(sl), len(ll), len(rl))
            sl += [''] * (row_h - len(sl))
            ll += [''] * (row_h - len(ll))
            rl += [''] * (row_h - len(rl))
            for i in range(row_h):
                L.append(hrow(sl[i], ll[i], rl[i]))
            L.append(row_sep)

        if not self.skipped:
            L.append('  (none)')
        else:
            L[-1] = hdr_sep

        L += ['', '=' * W]
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(L) + '\n')
        print(f'Log: {self.path}')
```

### When to call `log.record()` vs `log.skip()`

| Situation | Call |
|---|---|
| Replaced a cyan block with real SQL data | `log.record(section, 'Replaced', sql_file=..., rows=N, sz=sz, max_len=max_len, notes=[...])` |
| Removed cyan from a single field (e.g. SID, DB version) | `log.record(section, 'Filled field', detail='...')` |
| Fixed `Database: …` placeholders | `log.record('Section headers', 'Filled Database: field', detail=f'{N} occurrences → Database: {SID}')` |
| Replaced narrative text (e.g. OS/kernel paragraph) | `log.record(section, 'Replaced narrative', detail='...')` |
| Left cyan — no SQL data available (ABAP, MDC tenant limit, etc.) | `log.skip(section, reason, heading='Nearest heading text', para_idx=<para index>)` |
| Left cyan — customer-specific content | `log.skip(section, 'Customer-specific analysis — requires manual input', heading='...', para_idx=N)` |

**Always pass `heading` and `para_idx` to `log.skip()`** so the log's "Blocks left cyan" table shows the exact document location. Find the heading by scanning for `AUTONUMLGL` paragraphs near the skipped block.

### Usage pattern in a script

```python
import datetime

# At the top, after detecting system info:
log = ChangeLog(LOG, INPUT, OUTPUT, SID, VERSION, HOST, OS_STR)
cyan_before = sum(1 for p in paras if 'cyan' in p)
para_before = len(paras)

# After each replacement — pass sz, max_len, notes for rich log output:
log.record('SAP HANA Overview (3.2.1)', 'Replaced',
           sql_file='HANA_Configuration_Overview_2.00.040+.txt',
           rows=len(result_rows), sz=14, max_len=106)

log.record('Section headers', 'Filled Database: field',
           detail=f'15 occurrences → Database: {SID}')

# Skipped blocks — always provide heading and para_idx so the log shows location:
log.skip('SAP ABAP Overview', 'No ABAP system — section not applicable',
         heading='SAP ABAP Overview', para_idx=1221)

log.skip('MDC Overview', 'MDC SQL fails on tenant DB context (SYS_DATABASES unavailable)',
         heading='SAP HANA Overview', para_idx=1072)

# At the very end, before sys.exit / after saving the docx:
cyan_after = sum(1 for p in paras_final if 'cyan' in p)
para_after = len(paras_final)
log.write(cyan_before, cyan_after, para_before, para_after)
```

### What the log must capture for every change

For **SQL block replacements**: section name, SQL file used, number of result rows inserted, font size (`sz`), max line length (`max_len`), and any parameter changes or column notes (`notes`).

For **field replacements** (SID, version, OS, `Database: …`): what was replaced and how many occurrences.

For **narrative replacements** (e.g. OS/kernel summary text): a one-line description of what old text was replaced with.

For **skipped cyan blocks**: the section name, the reason (ABAP N/A, MDC tenant limit, customer-specific, no SQL file available, etc.), the nearest document heading, and the paragraph index — so the consultant can navigate directly to the right place.

## Scripts

- `update_sections.py` — replaces sections 3.3–5 cyan blocks with real HANA SQL results
- `update_section5.py` — handles all section 5 cyan block replacements
- `fix_section5.py` — resizes table blocks and strips Courier New from non-table paragraphs

## Backups

The report has sequential backups: `.bak` (original template), `.bak2` through `.bak8`.
