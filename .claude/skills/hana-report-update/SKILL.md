---
name: hana-report-update
description: This skill should be used when the user asks to update, fill in, or process a SAP HANA MiniCheck report (.docx), replace cyan placeholders with real SQL data, fix table formatting, or update system ID fields in the report. Input and output filenames are passed as $ARGUMENTS.
version: 2.0.0
---

# SAP HANA MiniCheck Report Update

This skill covers how to process and update a SAP HANA MiniCheck report `.docx` file by replacing template placeholders with real data from the HANA system.

**Arguments**: `$ARGUMENTS` contains the input and (optionally) output filename, e.g.:
- `/hana-report-update HAN_report.docx` → input and output are both `HAN_report.docx`
- `/hana-report-update HAN_report.docx HAN_report_updated.docx` → separate input and output

Parse at the top of the script:
```python
import sys
args = "$ARGUMENTS".split()
INPUT  = args[0] if len(args) >= 1 else 'report.docx'
OUTPUT = args[1] if len(args) >= 2 else INPUT
shutil.copy(INPUT, INPUT + '.bak')  # always back up the input
```
Use `INPUT` to load the document and `OUTPUT` to save the result. This way the original is never overwritten when a separate output filename is given.

## Overview

The report is a `.docx` file (ZIP archive). All content lives in `word/document.xml`. Paragraphs are split with `re.split(r'(?=<w:p[ >])', body)`. Tables are embedded within paragraph nodes.

## Key Technical Concepts

- **Cyan highlight detection**: `'cyan' in para_xml` identifies unreplaced sample data
- **Contiguous cyan block scanning**: scan forward with `max_gap=5` tolerance to find block boundaries
- **Reverse-order replacement**: apply replacements from highest to lowest index to preserve validity
- **A4 page width math**: usable = 9099 twips; `Courier New` char width at sz=14 (7pt) ≈ 84 twips → **108 chars max**; at sz=16 (8pt) ≈ 96 twips → **94 chars max**. **Every line must stay within these limits — no wrapping allowed.**
- **Font for SQL output**: `Courier New` — equal-width characters ensure column alignment.
- **Font size convention**: `w:val` is in half-points. Use `w:val="16"` (8pt) when max line ≤94 chars, `w:val="14"` (7pt) when 94–108 chars, trim columns if >108 chars.
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
2. From the matches, pick the file whose version suffix is the **highest that is ≤ the system revision**
3. Read the file header (`[NAME]`, `[DESCRIPTION]`, `[VALID FOR]`) to confirm it covers what you need
4. Execute with `mcp__sap-hana-onprem__execute_sql_file` using the full path

### Version selection — detect dynamically each run

**Step 0 (always first)**: query the live system revision before selecting any SQL file:
```sql
SELECT VALUE FROM M_SYSTEM_OVERVIEW WHERE NAME = 'Version'
```
or read it from the document's already-filled `HANA_Configuration_Overview` block (e.g. `|Revision |2.00.059.20...`).

Use the detected revision (e.g. `2.00.059`) to apply the rule:
- ✓ Use any file whose version suffix is **≤ detected revision** (e.g. `2.00.040+`, `2.00.030+`, `2.00.000+`, `1.00.90+_MDC`, no-suffix)
- ✗ Skip files whose version suffix is **> detected revision** (e.g. if revision is 2.00.059, skip `2.00.060+` and above)
- When multiple valid versions exist, always pick the **highest** that still qualifies
- Never assume the version — always detect it fresh for each new document/system

## Document Structure and SQL File Mapping

### How to approach a new document

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
     - `max_len > 108` → **must trim columns** before inserting: drop the least important column(s) until `max_len ≤ 108`, then use `sz=14`; add a `-- (column X removed for width)` comment line after the header separator
   - Apply `make_para(line, sz)` for every line in the block — including header, separator, data rows, and footer
   - Never mix font sizes within the same SQL output block
   - **Verify before inserting**: `assert max(len(l) for l in lines) <= 108` — if any line still exceeds the limit, trim further
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

### Full SQL File Mapping (version-agnostic)

Always apply the dynamic version selection rule above when choosing the file. The table below lists the correct file pattern — substitute the highest valid version for the actual system.

| Report Section | SQL Reference in Doc | SQL File to Use | Notes |
|---|---|---|---|
| SAP HANA Overview (General Info) | `HANA_Configuration_Overview` | `HANA_Configuration_Overview_2.00.040+.txt` | General config, versions, features, deprecated |
| Infrastructure Report (section 3.2.1) | `HANA_Configuration_Infrastructure` | `HANA_Configuration_Infrastructure_2.00.040+.txt` | Hosts, CPU, memory, OS, disk, network. Appears **immediately after** the `HANA_Configuration_Overview` table — do NOT over-run the Overview replacement boundary or this block will be deleted. |
| SAP HANA Workload Information | `HANA_Workload` | `HANA_Workload_1.00.90+_MDC.txt` | Per-day load overview (EXEC_PER_S etc.) — FAILS on tenant DB with `invalid schema name: SYS_DATABASES`; fallback `HANA_Workload.txt` only gives current-moment data, not historical |
| SAP HANA Load History (per hour) | `HANA_LoadHistory_Services` | `HANA_LoadHistory_Services_2.00.030+.txt` | Copy to `/tmp/hana_loadhistory_hour.txt`, change `'DAY' TIME_AGGREGATE_BY` → `'HOUR' TIME_AGGREGATE_BY`, then execute the temp file |
| Workload Management Settings | `HANA_Workload_WorkloadClasses` | `HANA_Workload_WorkloadClasses_2.00.040+.txt` | ESS/statistics workload class |
| Space – Largest Tables | `HANA_Tables_LargestTables` | `HANA_Tables_LargestTables_2.00.040+.txt` | Top tables by size |
| Space – Table Classes | `HANA_Tables_TableClasses` | `HANA_Tables_TableClasses.txt` | Table class distribution |
| Space – Partitioning Overview | `HANA_Tables_ColumnStore_PartitionedTables` | `HANA_Tables_ColumnStore_PartitionedTables_2.00.000+.txt` | Partitioned tables |
| Memory Overview | `HANA_Memory_Overview` | `HANA_Memory_Overview_2.00.040+.txt` | Physical/HANA/global alloc memory |
| Audit Policies | `HANA_Security_AuditPolicies` | `HANA_Security_AuditPolicies_1.00.80+.txt` | Configured audit policies |
| System Replication | `HANA_Replication_SystemReplication_Overview` | `HANA_Replication_SystemReplication_Overview_1.00.120+_MDC.txt` | Replication state, lag, backlog |
| Triggers | `HANA_Configuration_Triggers` | `HANA_Configuration_Triggers.txt` | Configured triggers by scenario |
| SAP HANA Mini Checks | `HANA_Configuration_MiniChecks` | highest `HANA_Configuration_MiniChecks_<version>.txt` ≤ system revision | Full mini check suite |
| SAP HANA Trace File Mini Checks | `HANA_TraceFiles_MiniChecks` | `HANA_TraceFiles_MiniChecks.txt` | Trace file error patterns |
| SAP HANA Call Stack Mini Checks | `HANA_Threads_Callstacks_MiniChecks` | `HANA_Threads_Callstacks_MiniChecks_2.00.040+.txt` | Call stack anomaly checks |
| Runtime Tests | `HANA_Tests_Results` | `HANA_Tests_Results.txt` | Arithmetic/memory/string test results |
| Service Startup Times | `HANA_Startup_StartupTimes` | `HANA_Startup_StartupTimes.txt` | Port startup delay analysis (use no-suffix version for MDC) |
| Unsupported OS / Outdated Kernel | `HANA_Configuration_Infrastructure` | `HANA_Configuration_Infrastructure_2.00.040+.txt` | Same infra SQL, HOST/OS columns |
| Host Memory Overallocation / IPMM | `HANA_Configuration_Infrastructure` | `HANA_Configuration_Infrastructure_2.00.040+.txt` | MEMORY_GB, ALLOC_LIM columns |
| Timezone Configuration | `HANA_Configuration_Timezones` | `HANA_Configuration_Timezones_2.00.040+.txt` | Host TZ, TZ tables, TZ parameters |
| SQL Cache – Statistics Server | `HANA_SQL_SQLCache` | `HANA_SQL_SQLCache_2.00.053+.txt` | Aggregated by schema/category |
| SQL Cache – Specific Tables | `HANA_SQL_SQLCache` | `HANA_SQL_SQLCache_2.00.053+.txt` | Same file, filter by table |
| Data Retention (Statistics Server) | `HANA_StatisticsServer_Histories_RetentionTime` | `HANA_StatisticsServer_Histories_RetentionTime_2.00.040+.txt` | DEF_DAYS, CUR_DAYS, OLDEST_DAYS |
| Backup Runs | `HANA_Backups_BackupRuns` | `HANA_Backups_BackupRuns_1.00.90+_MDC.txt` | DATA_BACKUP entries (use no-suffix if MDC version errors) |
| License | `HANA_License_Overview` | `HANA_License_Overview.txt` | Limit, usage, expiry |
| Consistency Checks | `HANA_Consistency_CheckTableConsistency_Executions` | `HANA_Consistency_CheckTableConsistency_Executions_2.00.040+.txt` | Scheduled check runs |
| Deprecated Features | `HANA_Configuration_Overview` | `HANA_Configuration_Overview_2.00.040+.txt` | DEPRECATED_FEATURES section |
| Statement Hints | `HANA_SQL_PlanStability_StatementHints` | `HANA_SQL_PlanStability_StatementHints_2.00.040+.txt` | Delivered statement hints status |
| Runtime Checks (section 4.5) | `HANA_Tests_Results` | `HANA_Tests_Results.txt` | **Must run prerequisites first** (each 3× via MCP): `HANA_Tests_ArithmeticOperations.txt`, `HANA_Tests_MemoryOperations.txt`, `HANA_Tests_StringOperations.txt` — then execute `HANA_Tests_Results.txt`. Drop `TEST_COMMAND` column if width >108 chars. |


### Version Selection Rules
- Always detect the system revision first (see Step 0 above) — do NOT hardcode
- Use any file whose version suffix is ≤ detected revision
- Use no-version-suffix files ✓ (valid for all revisions)
- When multiple valid versions exist, always pick the **highest** that still qualifies
- If a MDC-specific file (`1.00.90+_MDC`) throws `invalid schema name: SYS_DATABASES`, fall back to the plain no-suffix version of the same SQL

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

- **Affected case**: replacing `HANA_Configuration_Overview` (section 3.2.1) with too large a range deleted the `HANA_Configuration_Infrastructure` intro text and template cyan block that immediately follows.
- **Fix**: after replacement, verify that the paragraph immediately after the new block matches what was in the original document at that position.
- **Recovery**: if a block is missing from output but present in input, extract it from the input `.bak` file, execute the correct SQL, and re-insert at the correct position.

### 2. `Database: …` split-run pattern never matched by simple replace
`Database:` and ` …` are in **separate `<w:r>` runs** in the XML. A plain `str.replace('Database: …', ...)` will never match. Use a cross-run regex (see step 8).

### 3. MDC SQL files fail on tenant DB
Files ending in `_MDC` (e.g. `HANA_Workload_1.00.90+_MDC.txt`) reference `SYS_DATABASES` which does not exist in a tenant DB context. Fall back to the no-suffix version, but note it may only return current-moment data (not historical).

### 4. TIME_AGGREGATE_BY defaults to DAY — change to HOUR for hourly blocks
`HANA_LoadHistory_Services_2.00.030+.txt` defaults to `'DAY'`. For hourly output, copy to a temp file and change `'DAY' TIME_AGGREGATE_BY` → `'HOUR' TIME_AGGREGATE_BY` before executing.

### 5. Runtime Checks require prerequisite test runs
`HANA_Tests_Results.txt` reads from `M_SQL_PLAN_CACHE_RESET` and returns empty unless the three test SQLs have been executed first (each at least 3×): `HANA_Tests_ArithmeticOperations.txt`, `HANA_Tests_MemoryOperations.txt`, `HANA_Tests_StringOperations.txt`.

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

def make_para_courier(text, sz):
    """Courier New paragraph at given half-point size (sz=14→7pt, sz=16→8pt)."""
    txt = xml_escape(text)
    space_attr = ' xml:space="preserve"' if text.startswith(' ') or '  ' in text else ''
    return (
        '<w:p><w:pPr><w:jc w:val="left"/></w:pPr>'
        '<w:r>'
        f'<w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>'
        f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
        f'<w:t{space_attr}>{txt}</w:t>'
        '</w:r></w:p>'
    )
```

## Change Log

Every report update run **must** produce a log file alongside the output document. The log file documents every change made so the consultant can review what was automated vs. what still needs manual attention.

### Log file naming

```python
import os, datetime
LOG = os.path.splitext(OUTPUT)[0] + '_update_log.txt'
```

Example: `HAN_report.docx` → `HAN_report_update_log.txt`

### ChangeLog helper class

Include this class at the top of every update script, after the imports:

```python
class ChangeLog:
    def __init__(self, path, input_file, output_file, sid, version, host, os_str):
        self.path = path
        self.entries = []
        self.skipped = []
        self.start_time = datetime.datetime.now()
        self.meta = {
            'input': input_file, 'output': output_file,
            'sid': sid, 'version': version, 'host': host, 'os': os_str,
        }

    def record(self, section, action, detail='', rows=0, sql_file=''):
        """Record a completed replacement."""
        self.entries.append({
            'section': section, 'action': action,
            'detail': detail, 'rows': rows, 'sql_file': sql_file,
            'time': datetime.datetime.now().strftime('%H:%M:%S'),
        })

    def skip(self, section, reason):
        """Record a block intentionally left cyan."""
        self.skipped.append({'section': section, 'reason': reason})

    def write(self, cyan_before, cyan_after, para_before, para_after):
        lines = []
        lines.append('=' * 72)
        lines.append('SAP HANA MiniCheck Report Update Log')
        lines.append('=' * 72)
        lines.append(f"Date/Time : {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Input     : {self.meta['input']}")
        lines.append(f"Output    : {self.meta['output']}")
        lines.append(f"SID       : {self.meta['sid']}")
        lines.append(f"Version   : {self.meta['version']}")
        lines.append(f"Host      : {self.meta['host']}")
        lines.append(f"OS        : {self.meta['os']}")
        lines.append('')
        lines.append('-' * 72)
        lines.append(f'SUMMARY')
        lines.append('-' * 72)
        lines.append(f"  Paragraphs : {para_before} → {para_after}")
        lines.append(f"  Cyan paras : {cyan_before} → {cyan_after}  ({cyan_before - cyan_after} replaced)")
        lines.append(f"  Replacements made : {len(self.entries)}")
        lines.append(f"  Blocks left cyan  : {len(self.skipped)}")
        lines.append('')
        lines.append('-' * 72)
        lines.append('REPLACEMENTS MADE')
        lines.append('-' * 72)
        for e in self.entries:
            lines.append(f"  [{e['time']}] {e['section']}")
            lines.append(f"    Action  : {e['action']}")
            if e['sql_file']:
                lines.append(f"    SQL file: {e['sql_file']}")
            if e['rows']:
                lines.append(f"    Rows    : {e['rows']}")
            if e['detail']:
                lines.append(f"    Detail  : {e['detail']}")
        lines.append('')
        lines.append('-' * 72)
        lines.append('BLOCKS LEFT CYAN (require manual attention)')
        lines.append('-' * 72)
        for s in self.skipped:
            lines.append(f"  {s['section']}")
            lines.append(f"    Reason: {s['reason']}")
        lines.append('')
        lines.append('=' * 72)
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        print(f'Log written to {self.path}')
```

### When to call `log.record()` vs `log.skip()`

| Situation | Call |
|---|---|
| Replaced a cyan block with real SQL data | `log.record(section, 'Replaced', sql_file=..., rows=N)` |
| Removed cyan from a single field (e.g. SID, DB version) | `log.record(section, 'Filled field', detail='...')` |
| Fixed `Database: …` placeholders | `log.record('Section headers', 'Filled Database: field', detail=f'{N} occurrences → Database: {SID}')` |
| Replaced narrative text (e.g. OS/kernel paragraph) | `log.record(section, 'Replaced narrative', detail='...')` |
| Left cyan — no SQL data available (ABAP, MDC tenant limit, etc.) | `log.skip(section, reason)` |
| Left cyan — customer-specific content | `log.skip(section, 'Customer-specific analysis — requires manual input')` |

### Usage pattern in a script

```python
import datetime

# At the top, after detecting system info:
log = ChangeLog(LOG, INPUT, OUTPUT, SID, VERSION, HOST, OS)
cyan_before = sum(1 for p in paras if 'cyan' in p)
para_before = len(paras)

# After each replacement:
log.record('SAP HANA Overview (3.2.1)', 'Replaced',
           sql_file='HANA_Configuration_Overview_2.00.040+.txt', rows=len(result_rows))

log.record('Section headers', 'Filled Database: field',
           detail=f'15 occurrences → Database: {SID}')

log.skip('SAP ABAP Overview', 'No ABAP system — section not applicable')

log.skip('MDC Overview', 'MDC SQL fails on tenant DB context (SYS_DATABASES unavailable)')

# At the very end, before sys.exit / after saving the docx:
cyan_after = sum(1 for p in paras_final if 'cyan' in p)
para_after = len(paras_final)
log.write(cyan_before, cyan_after, para_before, para_after)
```

### What the log must capture for every change

For **SQL block replacements**: section name, SQL file used, number of result rows inserted.

For **field replacements** (SID, version, OS, `Database: …`): what was replaced and how many occurrences.

For **narrative replacements** (e.g. OS/kernel summary text): a one-line description of what old text was replaced with.

For **skipped cyan blocks**: the section name and the reason (ABAP N/A, MDC tenant limit, customer-specific, no SQL file available, etc.).

## Scripts

- `update_sections.py` — replaces sections 3.3–5 cyan blocks with real HANA SQL results
- `update_section5.py` — handles all section 5 cyan block replacements
- `fix_section5.py` — resizes table blocks and strips Courier New from non-table paragraphs

## Backups

The report has sequential backups: `.bak` (original template), `.bak2` through `.bak8`.
