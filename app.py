from flask import Flask, jsonify, render_template, request
import re

app = Flask(__name__)


def normalize_whitespace(sql: str) -> str:
    """Trim extra whitespace around the query."""
    return sql.strip()


def remove_sql_server_specific_statements(sql: str) -> str:
    """Remove common SQL Server-only control statements that are not valid in MySQL."""
    sql = re.sub(r"(?im)^\s*SET\s+NOCOUNT\s+ON\s*;?\s*$", "-- SQL Server NOCOUNT removed for MySQL migration", sql)
    sql = re.sub(r"(?im)^\s*SET\s+ANSI_NULLS\s+ON\s*;?\s*$", "", sql)
    sql = re.sub(r"(?im)^\s*SET\s+QUOTED_IDENTIFIER\s+ON\s*;?\s*$", "", sql)
    sql = re.sub(r"(?im)^\s*GO\s*$", ";\n", sql)
    sql = re.sub(r"\bdbo\.", "", sql)
    return sql


def convert_data_types(sql: str) -> str:
    """Convert common SQL Server data types to MySQL-friendly ones."""
    sql = re.sub(r"\bNVARCHAR\s*\(\s*(MAX|\d+)\s*\)", lambda m: "TEXT" if m.group(1).upper() == "MAX" else f"VARCHAR({m.group(1)})", sql, flags=re.I)
    sql = re.sub(r"\bNCHAR\s*\(\s*(MAX|\d+)\s*\)", lambda m: "CHAR(255)" if m.group(1).upper() == "MAX" else f"CHAR({m.group(1)})", sql, flags=re.I)
    sql = re.sub(r"\bDATETIME2\b", "DATETIME", sql, flags=re.I)
    sql = re.sub(r"\bSMALLDATETIME\b", "DATETIME", sql, flags=re.I)
    sql = re.sub(r"\bBIT\b", "TINYINT(1)", sql, flags=re.I)
    sql = re.sub(r"\bMONEY\b", "DECIMAL(19,4)", sql, flags=re.I)
    sql = re.sub(r"\bREAL\b", "FLOAT", sql, flags=re.I)
    sql = re.sub(r"\bUNIQUEIDENTIFIER\b", "CHAR(36)", sql, flags=re.I)
    return sql


def convert_top_to_limit(sql: str) -> str:
    """Convert TOP N to LIMIT N for each SELECT statement."""
    statements = []
    for statement in re.split(r"(?<!')\;(?!')", sql):
        if not statement.strip():
            continue
        match = re.search(r"\bTOP\s+(\d+)\b", statement, flags=re.I)
        if not match:
            statements.append(statement.strip())
            continue
        limit_value = match.group(1)
        updated = re.sub(r"\bTOP\s+\d+\b", "", statement, flags=re.I).strip()
        if updated.endswith(";"):
            updated = updated[:-1].rstrip()
        statements.append(f"{updated} LIMIT {limit_value}")
    return ";\n".join(statements).strip()


def convert_offset_fetch(sql: str) -> str:
    """Translate SQL Server OFFSET/FETCH pagination to MySQL LIMIT/OFFSET."""
    pattern = re.compile(r"\bOFFSET\s+(\d+)\s+ROWS\s+FETCH\s+NEXT\s+(\d+)\s+ROWS\s+ONLY", re.I)
    match = pattern.search(sql)
    if not match:
        return sql
    offset = match.group(1)
    row_count = match.group(2)
    return pattern.sub(f"LIMIT {row_count} OFFSET {offset}", sql, count=1)


def convert_getdate(sql: str) -> str:
    """Translate GETDATE(), SYSDATETIME(), and similar SQL Server date functions to MySQL equivalents."""
    sql = re.sub(r"\bGETDATE\s*\(\s*\)", "NOW()", sql, flags=re.I)
    sql = re.sub(r"\bSYSDATETIME\s*\(\s*\)", "NOW()", sql, flags=re.I)
    sql = re.sub(r"\bCURRENT_TIMESTAMP\b", "NOW()", sql, flags=re.I)
    return sql


def convert_isnull(sql: str) -> str:
    """Translate ISNULL() to IFNULL()."""
    return re.sub(r"\bISNULL\s*\(", "IFNULL(", sql, flags=re.I)


def convert_common_tsql_functions(sql: str) -> str:
    """Translate common SQL Server functions to MySQL equivalents."""
    sql = re.sub(r"\bTRIM\s*\(", "TRIM(", sql, flags=re.I)
    sql = re.sub(r"\bLEN\s*\(", "CHAR_LENGTH(", sql, flags=re.I)
    sql = re.sub(r"\bDATALENGTH\s*\(", "CHAR_LENGTH(", sql, flags=re.I)
    sql = re.sub(r"\bGETUTCDATE\s*\(\s*\)", "UTC_TIMESTAMP()", sql, flags=re.I)
    sql = re.sub(r"\bDATEADD\s*\(", "DATE_ADD(", sql, flags=re.I)
    sql = re.sub(r"\bDATEDIFF\s*\(", "DATEDIFF(", sql, flags=re.I)
    sql = re.sub(r"\bREPLACE\s*\(", "REPLACE(", sql, flags=re.I)
    sql = re.sub(r"\bSUBSTRING\s*\(", "SUBSTRING(", sql, flags=re.I)
    sql = re.sub(r"\bCHARINDEX\s*\(", "LOCATE(", sql, flags=re.I)
    sql = re.sub(r"\bSTUFF\s*\(", "STUFF(", sql, flags=re.I)
    sql = re.sub(r"\bDATEPART\s*\(", "EXTRACT(", sql, flags=re.I)
    return sql


def convert_create_table(sql: str) -> str:
    """Adjust CREATE TABLE syntax for MySQL, including IDENTITY and default expressions."""
    sql = re.sub(r"\bIDENTITY\s*\((\d+),\s*(\d+)\)", r"AUTO_INCREMENT", sql, flags=re.I)
    sql = re.sub(r"\bDEFAULT\s+NEWID\s*\(\s*\)", "DEFAULT UUID()", sql, flags=re.I)
    sql = re.sub(r"\bDEFAULT\s+GETDATE\s*\(\s*\)", "DEFAULT CURRENT_TIMESTAMP", sql, flags=re.I)
    sql = re.sub(r"\bDEFAULT\s+1\b", "DEFAULT 1", sql, flags=re.I)
    sql = re.sub(r"\bPRIMARY\s+KEY\b", "PRIMARY KEY", sql, flags=re.I)
    return sql


def convert_print_statements(sql: str) -> str:
    """Translate PRINT statements to SELECT or comments for MySQL."""
    return re.sub(r"(?im)^\s*PRINT\s+(.+?)\s*;?\s*$", lambda m: f"SELECT {m.group(1).strip()};", sql)


def convert_declare_to_set(sql: str) -> str:
    """Translate simple SQL Server DECLARE statements to MySQL-compatible SET statements."""
    pattern = re.compile(r"(?im)^\s*DECLARE\s+(@[A-Za-z_][A-Za-z0-9_]*)\s+[^=]+?=\s*(.+?)\s*;?\s*$")

    def replace_declare(match: re.Match) -> str:
        var_name = match.group(1)
        value = match.group(2).strip()
        return f"SET {var_name} := {value};"

    return pattern.sub(replace_declare, sql)


def convert_case_expressions(sql: str) -> str:
    """Preserve CASE expressions as-is because they are already portable in most cases."""
    return sql


def convert_ctes(sql: str) -> str:
    """Preserve CTE syntax for MySQL; most recursive CTEs need manual review."""
    return sql


def convert_joins(sql: str) -> str:
    """Keep JOIN syntax intact and note that SQL Server-specific join hints may need manual review."""
    sql = re.sub(r"\bINNER\s+JOIN\b", "INNER JOIN", sql, flags=re.I)
    sql = re.sub(r"\bLEFT\s+OUTER\s+JOIN\b", "LEFT JOIN", sql, flags=re.I)
    sql = re.sub(r"\bRIGHT\s+OUTER\s+JOIN\b", "RIGHT JOIN", sql, flags=re.I)
    return sql

def convert_temp_tables(sql: str) -> str:
    """Translate SQL Server temp tables to MySQL temporary tables."""
    sql = re.sub(r"\bSELECT\s+\*\s+INTO\s+#([A-Za-z0-9_]+)", r"CREATE TEMPORARY TABLE \1 AS SELECT *", sql, flags=re.I)
    sql = re.sub(r"\bDROP\s+TABLE\s+#([A-Za-z0-9_]+)", r"DROP TEMPORARY TABLE \1", sql, flags=re.I)
    sql = re.sub(r"#([A-Za-z0-9_]+)", r"\1", sql)
    return sql


def convert_update_from(sql: str) -> str:
    """Preserve UPDATE ... FROM statements because their semantics are not safely portable to MySQL without manual review."""
    return sql


def convert_merge_to_upsert(sql: str) -> str:
    """Translate simple MERGE statements into MySQL-style INSERT ... ON DUPLICATE KEY UPDATE."""
    pattern = re.compile(r"MERGE\s+([A-Za-z0-9_`\.]+)\s+AS\s+Target\s+USING\s*\((.*?)\)\s+AS\s+Source\s+ON\s+(.+?)\s+WHEN\s+MATCHED\s+THEN\s+UPDATE\s+SET\s+(.+?)\s+WHEN\s+NOT\s+MATCHED\s+THEN\s+INSERT\s*\((.*?)\)\s*VALUES\s*\((.*?)\)", re.I | re.S)
    match = pattern.search(sql)
    if not match:
        return sql

    table_name = match.group(1).strip()
    source_query = match.group(2).strip()
    update_set = match.group(4).strip()
    insert_columns = match.group(5).strip()
    insert_values = match.group(6).strip()

    update_items = []
    for part in update_set.split(","):
        part = part.strip()
        if "Target." in part and "=" in part:
            target_col = part.split("=", 1)[0].strip().replace("Target.", "")
            update_items.append(f"{target_col} = VALUES({target_col})")
        else:
            update_items.append(part)

    return f"INSERT INTO {table_name} ({insert_columns}) SELECT {insert_values} FROM ({source_query}) AS Source ON DUPLICATE KEY UPDATE {', '.join(update_items)};"


def convert_identifiers(sql: str) -> str:
    """Convert square-bracket identifiers like [table] to backticks while preserving quoted names and function calls."""
    string_placeholders = []

    def protect_strings(match: re.Match) -> str:
        placeholder = f"__STRING_{len(string_placeholders)}__"
        string_placeholders.append(match.group(0))
        return placeholder

    sql = re.sub(r"'(?:''|[^'])*'", protect_strings, sql)
    sql = re.sub(r"\[([^\]]+)\]", r"`\1`", sql)

    def replace_qualified_name(match: re.Match) -> str:
        left = match.group(1)
        right = match.group(2)
        if re.search(r"\s*\(", match.group(0)):
            return match.group(0)
        return f"`{left}`.`{right}`"

    sql = re.sub(r"(?<![\w`])([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)(?!\s*\()", replace_qualified_name, sql)
    for index, original in enumerate(string_placeholders):
        sql = sql.replace(f"__STRING_{index}__", original)
    return sql


def convert_insert_statements(sql: str) -> str:
    """Translate INSERT syntax for migration purposes without inventing missing values."""

    def normalize_identifier(value: str) -> str:
        value = value.strip()
        value = re.sub(r"\[([^\]]+)\]", r"\1", value)
        value = re.sub(r"^`([^`]+)`$", r"\1", value)
        if "." in value:
            value = value.split(".")[-1]
        value = re.sub(r"[\[\]`]", "", value).strip()
        if not value:
            return value
        if re.search(r"[^A-Za-z0-9_]", value):
            return f"`{value}`"
        return value

    def replace_insert(match: re.Match) -> str:
        table_ref = match.group(1).strip()
        column_list = match.group(2).strip()
        tail = match.group(3).strip()

        table_name = normalize_identifier(table_ref)
        if table_name and table_name != "dbo":
            table_name = f"`{table_name}`"

        columns = []
        for raw_column in column_list.split(","):
            raw_column = raw_column.strip()
            if not raw_column:
                continue
            column_name = normalize_identifier(raw_column)
            if column_name:
                columns.append(column_name)

        if not columns:
            return match.group(0)

        column_sql = ", ".join(columns)
        if tail and re.search(r"\bVALUES\b", tail, re.I):
            return f"INSERT INTO {table_name} ({column_sql}) {tail}"

        return f"INSERT INTO {table_name} ({column_sql})\nVALUES ()"

    return re.sub(r"\bINSERT\s+INTO\s+([A-Za-z0-9_.\[\]`]+)\s*\((.*?)\)(.*)", replace_insert, sql, flags=re.I | re.S)


def convert_identity(sql: str) -> str:
    """Convert IDENTITY to AUTO_INCREMENT."""
    return re.sub(r"\bIDENTITY\s*\([^)]*\)", "AUTO_INCREMENT", sql, flags=re.I)


def convert_string_concatenation(sql: str) -> str:
    """Convert simple string concatenation from + to CONCAT() without touching arithmetic expressions."""
    if "+" not in sql or "'" not in sql:
        return sql

    parts = [part.strip() for part in re.split(r"\s*\+\s*", sql)]
    if len(parts) <= 1:
        return sql
    if not all(re.search(r"'[^']*'", part) for part in parts):
        return sql
    return f"CONCAT({', '.join(parts)})"


def map_mysql_type(sql_server_type: str) -> str:
    """Map a few common SQL Server data types to MySQL equivalents."""
    mapped = sql_server_type.strip().upper()
    if mapped == "INT":
        return "SIGNED"
    if mapped == "VARCHAR":
        return "VARCHAR"
    if mapped == "NVARCHAR":
        return "VARCHAR"
    if mapped == "DATETIME2":
        return "DATETIME"
    if mapped == "BIT":
        return "TINYINT(1)"
    return mapped


def convert_try_cast_try_convert(sql: str) -> str:
    """Translate CAST/TRY_CAST/TRY_CONVERT to MySQL-friendly syntax."""

    def replace_cast(match: re.Match) -> str:
        expression = match.group(1).strip()
        tsql_type = match.group(2).strip()
        mapped = map_mysql_type(tsql_type)
        if mapped == "INT":
            mapped = "SIGNED"
        return f"CAST({expression} AS {mapped})"

    def replace_try_cast(match: re.Match) -> str:
        expression = match.group(1).strip()
        tsql_type = match.group(2).strip()
        mapped = map_mysql_type(tsql_type)
        if mapped == "INT":
            mapped = "SIGNED"
        return f"CAST({expression} AS {mapped})"

    def replace_try_convert(match: re.Match) -> str:
        tsql_type = match.group(1).strip()
        expression = match.group(2).strip()
        mapped = map_mysql_type(tsql_type)
        if mapped == "INT":
            mapped = "SIGNED"
        return f"CAST({expression} AS {mapped})"

    sql = re.sub(r"\bCAST\s*\(\s*(.*?)\s+AS\s+([A-Za-z0-9()]+)\s*\)", replace_cast, sql, flags=re.I)
    sql = re.sub(r"\bTRY_CAST\s*\(\s*(.*?)\s+AS\s+([A-Za-z0-9()]+)\s*\)", replace_try_cast, sql, flags=re.I)
    sql = re.sub(r"\bTRY_CONVERT\s*\(\s*([A-Za-z0-9()]+)\s*,\s*(.*?)\s*\)", replace_try_convert, sql, flags=re.I)
    sql = re.sub(r"\bCONVERT\s*\(\s*VARCHAR\s*\(\s*\d+\s*\)\s*,\s*([A-Za-z0-9_.`]+)\s*,\s*120\s*\)", r"DATE_FORMAT(\1, '%Y-%m-%d')", sql, flags=re.I)
    return sql


def convert_procedure_syntax(sql: str) -> str:
    """Adjust a few common procedure-call differences for MySQL."""
    sql = re.sub(r"\bEXEC(?:UTE)?\b", "CALL", sql, flags=re.I)
    return sql


def collect_warnings(sql: str) -> list[str]:
    """Warn about SQL Server features that may need manual review."""
    warnings = []

    if re.search(r"\bCLR\b", sql, flags=re.I):
        warnings.append("CLR functions are SQL Server-specific and need manual review.")
    if re.search(r"\bsys\.[A-Za-z_\.]+", sql, flags=re.I):
        warnings.append("System views such as sys.* are not directly available in MySQL.")
    if re.search(r"\bCROSS\s+APPLY\b|\bOUTER\s+APPLY\b|\bPIVOT\b|\bUNPIVOT\b", sql, flags=re.I):
        warnings.append("APPLY/PIVOT syntax is not automatically converted and may need a manual rewrite.")
    if re.search(r"\bNOLOCK\b", sql, flags=re.I):
        warnings.append("NOLOCK hints are SQL Server-specific and should be removed or reviewed.")
    if re.search(r"\bOUTPUT\b", sql, flags=re.I):
        warnings.append("OUTPUT clauses often require manual adjustment for MySQL.")
    if re.search(r"\b@@IDENTITY\b|\bSCOPE_IDENTITY\b|\bIDENT_CURRENT\b", sql, flags=re.I):
        warnings.append("Identity functions differ between SQL Server and MySQL.")
    if re.search(r"\bINSERT\s+INTO\b", sql, flags=re.I) and "VALUES" not in sql.upper():
        warnings.append("This INSERT statement is incomplete for execution because it does not include a VALUES clause. The converter only migrated the syntax.")
    if re.search(r"\bCASE\b", sql, flags=re.I):
        warnings.append("CASE expressions were preserved but should be reviewed for database-specific behavior.")
    if re.search(r"\bWITH\s+\w+\s+AS\b", sql, flags=re.I):
        warnings.append("CTEs were preserved; recursive or SQL Server-specific CTE patterns may need manual review.")
    if re.search(r"\bUPDATE\b[\s\S]{0,200}\bFROM\b", sql, flags=re.I):
        warnings.append("UPDATE ... FROM is SQL Server-specific and was preserved for manual review because its MySQL equivalent is not guaranteed.")
    if re.search(r"\bJOIN\b", sql, flags=re.I) and re.search(r"\bWITH\s*\(", sql, flags=re.I):
        warnings.append("Join hints and table hints may need manual review for MySQL compatibility.")
    if re.search(r"\bREPLACE\b|\bSUBSTRING\b|\bCHARINDEX\b|\bSTUFF\b|\bDATEPART\b", sql, flags=re.I):
        warnings.append("Some string/date functions were translated conservatively; verify the output for exact semantics.")

    return warnings


def convert_query(sql: str) -> tuple[str, list[str]]:
    """Run the conversion pipeline and return a MySQL-ready query with warnings."""
    sql = normalize_whitespace(sql)

    # Each helper handles one conversion rule so the logic stays easy to extend.
    sql = remove_sql_server_specific_statements(sql)
    sql = convert_data_types(sql)
    sql = convert_print_statements(sql)
    sql = convert_declare_to_set(sql)
    sql = convert_top_to_limit(sql)
    sql = convert_offset_fetch(sql)
    sql = convert_getdate(sql)
    sql = convert_isnull(sql)
    sql = convert_common_tsql_functions(sql)
    sql = convert_case_expressions(sql)
    sql = convert_ctes(sql)
    sql = convert_joins(sql)
    sql = convert_create_table(sql)
    sql = convert_temp_tables(sql)
    sql = convert_update_from(sql)
    sql = convert_merge_to_upsert(sql)
    sql = convert_insert_statements(sql)
    sql = convert_identifiers(sql)
    sql = convert_identity(sql)
    sql = convert_string_concatenation(sql)
    sql = convert_try_cast_try_convert(sql)
    sql = convert_procedure_syntax(sql)

    warnings = collect_warnings(sql)
    if not warnings:
        warnings.append("No obvious unsupported SQL Server features were detected.")

    return sql, warnings


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert_endpoint():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query") or request.form.get("query", "")

    if not query.strip():
        return jsonify({"converted": "", "warnings": ["Please enter a T-SQL query to convert."]})

    converted, warnings = convert_query(query)
    return jsonify({"converted": converted, "warnings": warnings})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
