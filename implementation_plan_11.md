# SQL-Based CSV Query Tool & Debug Directory

We will implement an in-memory SQLite parser to give the agent full SQL capabilities over CSV files, automatically handling hex/decimal standardizations.

## Changes

### `mcp_server.py`

- **Directory Initialization**:
  Add `os.makedirs("debug", exist_ok=True)` alongside the sandbox creation to ensure the directory exists.
- **Whitelist the `debug` directory**:
  Append `debug` to `WORKSPACE_ALLOWED_WRITE_DIRS`. Modify `list_directory`, `read_source_file`, and `grep_codebase` sandbox conditions to permit reading from the `debug` folder.
- **Add `query_csv_sql` Tool**:
  Implement `@mcp.tool() def query_csv_sql(filepath: str, sql_query: str) -> str:`.
  - Validate sandboxing rules for `filepath`.
  - Open the CSV utilizing Python's native `csv.reader`.
  - Instantiate an in-memory database: `sqlite3.connect(':memory:')`.
  - Convert all hex string cells (`0xA`) and decimal string cells into proper integers during insertion so SQLite evaluates them as numbers natively.
  - Execute the provided `sql_query` against the `csv_data` table.
  - Return all matching row dictionaries converted to a JSON string.
