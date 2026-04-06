#!/usr/bin/env python3
"""SAP HANA MCP Server — exposes HANA database operations as MCP tools."""

import os
import json
from mcp.server.fastmcp import FastMCP
from hdbcli import dbapi

mcp = FastMCP("sap-hana")

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _connect() -> dbapi.Connection:
    host = os.environ["HANA_HOST"]
    user = os.environ["HANA_USER"]
    password = os.environ["HANA_PASSWORD"]

    # HANA_TYPE=cloud  → encrypted, port 443, validate cert
    # HANA_TYPE=onprem → unencrypted, port 30015, skip cert validation
    hana_type = os.environ.get("HANA_TYPE", "cloud").lower()
    if hana_type == "onprem":
        default_port = 30015
        default_encrypt = False
        default_validate_cert = False
    else:
        default_port = 443
        default_encrypt = True
        default_validate_cert = True

    port = int(os.environ.get("HANA_PORT", default_port))
    encrypt = os.environ.get("HANA_ENCRYPT", str(default_encrypt)).lower() == "true"
    validate_cert = os.environ.get("HANA_VALIDATE_CERT", str(default_validate_cert)).lower() == "true"

    return dbapi.connect(
        address=host,
        port=port,
        user=user,
        password=password,
        encrypt=encrypt,
        sslValidateCertificate=validate_cert,
    )


def _rows_to_json(cursor) -> str:
    cols = [d[0] for d in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    return json.dumps(rows, default=str)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def execute_sql(query: str) -> str:
    """Execute a SQL query and return results as JSON.

    Args:
        query: The SQL statement to execute (SELECT, INSERT, UPDATE, DELETE, etc.)
    """
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        if cursor.description:
            return _rows_to_json(cursor)
        conn.commit()
        return json.dumps({"rowcount": cursor.rowcount})
    finally:
        conn.close()


@mcp.tool()
def list_schemas() -> str:
    """List all schemas visible to the current user."""
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT SCHEMA_NAME FROM SYS.SCHEMAS "
            "WHERE HAS_PRIVILEGES = 'TRUE' ORDER BY SCHEMA_NAME"
        )
        schemas = [row[0] for row in cursor.fetchall()]
        return json.dumps(schemas)
    finally:
        conn.close()


@mcp.tool()
def list_tables(schema: str) -> str:
    """List all tables and views in a schema.

    Args:
        schema: The schema name to inspect (case-sensitive).
    """
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT TABLE_NAME, TABLE_TYPE FROM SYS.TABLES "
            "WHERE SCHEMA_NAME = ? ORDER BY TABLE_NAME",
            (schema,),
        )
        return _rows_to_json(cursor)
    finally:
        conn.close()


@mcp.tool()
def describe_table(schema: str, table: str) -> str:
    """Describe the columns of a table including data types and nullability.

    Args:
        schema: The schema name (case-sensitive).
        table:  The table name (case-sensitive).
    """
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COLUMN_NAME, DATA_TYPE_NAME, LENGTH, SCALE, IS_NULLABLE, "
            "DEFAULT_VALUE, COMMENTS "
            "FROM SYS.TABLE_COLUMNS "
            "WHERE SCHEMA_NAME = ? AND TABLE_NAME = ? "
            "ORDER BY POSITION",
            (schema, table),
        )
        return _rows_to_json(cursor)
    finally:
        conn.close()


@mcp.tool()
def execute_sql_file(file_path: str) -> str:
    """Execute a SQL script from a local file and return results as JSON.

    Args:
        file_path: Absolute path to the .sql file to execute.
    """
    if not os.path.isfile(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})
    with open(file_path, "r", encoding="utf-8") as f:
        query = f.read()
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        if cursor.description:
            return _rows_to_json(cursor)
        conn.commit()
        return json.dumps({"rowcount": cursor.rowcount})
    finally:
        conn.close()


@mcp.tool()
def call_stored_procedure(schema: str, procedure: str, params: str = "[]") -> str:
    """Call a stored procedure and return output parameters and result sets.

    Args:
        schema:    The schema containing the procedure (case-sensitive).
        procedure: The procedure name (case-sensitive).
        params:    JSON array of positional input parameters, e.g. [1, "hello"].
    """
    conn = _connect()
    try:
        cursor = conn.cursor()
        args = json.loads(params)
        placeholders = ", ".join("?" * len(args))
        call_stmt = f'CALL "{schema}"."{procedure}"({placeholders})'
        cursor.callproc(f'"{schema}"."{procedure}"', args) if not args else cursor.execute(call_stmt, args)
        results = []
        # Collect all result sets
        while True:
            if cursor.description:
                results.append(json.loads(_rows_to_json(cursor)))
            if not cursor.nextset():
                break
        return json.dumps(results, default=str)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
