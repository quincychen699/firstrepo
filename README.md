# SAP HANA MiniCheck Report Generator

Runs the SAP HANA MiniCheck SQL script against an on-premise or cloud HANA system and generates a Word report in TPO (Technical Performance Optimization) format.

## Prerequisites

- Python 3.10+
- SAP HANA client (`hdbcli`) — requires SAP software access
- Claude Code CLI with MCP support

## Setup

### 1. Install Python dependencies

```bash
cd sap-hana-mcp
python3 -m venv .venv
.venv/bin/pip install mcp hdbcli python-docx
```

### 2. Configure Claude Code MCP server

Add the following to your `~/.claude.json` under `mcpServers`:

```json
"sap-hana-onprem": {
  "type": "stdio",
  "command": "/path/to/sap-hana-mcp/.venv/bin/python",
  "args": ["/path/to/sap-hana-mcp/server.py"],
  "env": {
    "HANA_TYPE": "onprem",
    "HANA_HOST": "<your-hana-host>",
    "HANA_PORT": "30015",
    "HANA_USER": "<your-user>",
    "HANA_PASSWORD": "<your-password>"
  }
}
```

For HANA Cloud, use `"HANA_TYPE": "cloud"` and set `"HANA_PORT": "443"`.

### 3. Place required files

- `HANA_Configuration_MiniChecks.txt` — MiniCheck SQL script (SAP Note 1969700)
- `TPO_template.docx` — TPO template document (from your SAP engagement)

Update the file paths in `generate_minicheck_report.py` if needed:
```python
TEMPLATE_PATH = '/path/to/TPO_template.docx'
OUTPUT_PATH   = '/path/to/MiniCheck_Report.docx'
```

## Usage

### Option A: Claude Code skill (recommended)

In Claude Code, run:
```
/minicheck-report [output-filename.docx]
```

Claude will:
1. Execute the MiniCheck SQL against your HANA system
2. Parse all critical findings (C=X)
3. Generate the Word report with TPO-format recommendations
4. Show a summary table of all findings

### Option B: Run the script directly

```bash
.venv/bin/python generate_minicheck_report.py MyReport.docx
```

Then open the `.docx` in Word and press **Ctrl+A → F9** to update the table of contents.

## Files

| File | Description |
|------|-------------|
| `sap-hana-mcp/server.py` | MCP server exposing HANA tools to Claude |
| `sap-hana-mcp/pyproject.toml` | Python package dependencies |
| `generate_minicheck_report.py` | Word report generator |
| `HANA_Configuration_MiniChecks.txt` | MiniCheck SQL (SAP Note 1969700) |
| `TPO_template.docx` | TPO report template |
| `.claude/skills/minicheck-report/SKILL.md` | Claude Code skill — generate MiniCheck report |
| `.claude/skills/hana-report-update/SKILL.md` | Claude Code skill — update existing report with live data |

---

## Skill: hana-report-update

Automates filling in a SAP HANA MiniCheck `.docx` report by replacing all cyan-highlighted placeholder blocks with real data queried live from the HANA system.

### What it does

1. Detects system SID, version, host, and OS from the live HANA instance
2. Replaces every cyan placeholder block with the corresponding live SQL output (Courier New, fixed-width, sized to fit A4 width)
3. Fills in all system identity fields (`Database: …`, SAP System ID, DB Version, OS) throughout the document
4. Leaves intentionally unfilled blocks cyan (ABAP sections, customer-specific analysis, MDC data not accessible from tenant DB) so they are easy to identify
5. Produces a change log file (`<report>_update_log.txt`) documenting every replacement and every block left for manual attention

### Usage

```
/hana-report-update <input.docx> [output.docx]
```

Examples:
```
/hana-report-update HAN_report.docx
/hana-report-update HAN_report.docx HAN_report_filled.docx
```

### Requirements

- Live HANA system accessible via the `sap-hana-onprem` MCP server (see Setup above)
- `SQLStatements/` folder containing the SAP Note 1969700 SQL files
- Python 3.10+

### Output

| Output file | Description |
|---|---|
| `<output>.docx` | Updated report with cyan placeholders replaced |
| `<output>_update_log.txt` | Change log listing every replacement and skipped block |

---

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `execute_sql` | Run a SQL query and return JSON results |
| `execute_sql_file` | Execute a SQL script from a local file |
| `list_schemas` | List all schemas |
| `list_tables` | List tables in a schema |
| `describe_table` | Describe columns of a table |
| `call_stored_procedure` | Call a stored procedure |
