# smartsheet-mcp

A **local [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server** written in Python. It exposes Smartsheet [REST API v2](https://developers.smartsheet.com/api/smartsheet/introduction) operations as MCP tools so assistants in **Cursor**, Claude Desktop, and other MCP clients can read and update sheets with less boilerplate.

Smartsheet is a trademark of Smartsheet Inc. This project is not affiliated with or endorsed by Smartsheet.

## Requirements

- Python **3.10+**
- A Smartsheet **personal access token** with access to the sheets you need. API access follows Smartsheet’s product and developer terms; see the [API introduction](https://developers.smartsheet.com/api/smartsheet/introduction).

## Quick start

```bash
git clone <your-repo-url>
cd <repository-root>
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Set the token in the environment (see [`.env.example`](./.env.example)):

| Variable | Required | Description |
|----------|----------|-------------|
| `SMARTSHEET_ACCESS_TOKEN` | Yes | Bearer token for `Authorization` |
| `SMARTSHEET_BASE_URL` | No | Default `https://api.smartsheet.com/2.0`. Use Gov/EU/AU bases if your account requires them (same docs as above). |

Run the server (stdio, for MCP clients):

```bash
export SMARTSHEET_ACCESS_TOKEN="your-token"
smartsheet-mcp
# equivalent: python -m smartsheet_mcp
```

The process exits immediately with a message on stderr if `SMARTSHEET_ACCESS_TOKEN` is unset.

## Cursor (and other MCP clients)

Add a stdio server that points at this repo’s interpreter and module, and pass the token via `env` (do not commit real tokens):

```json
{
  "mcpServers": {
    "smartsheet": {
      "command": "/absolute/path/to/smartsheet/.venv/bin/python",
      "args": ["-m", "smartsheet_mcp"],
      "env": {
        "SMARTSHEET_ACCESS_TOKEN": "your-token-here"
      }
    }
  }
}
```

Restart Cursor (or reload MCP) after editing configuration.

## Tools overview

Tools return JSON. Smartsheet errors are usually surfaced as objects with an `error` field (and optional `smartsheet` payload) instead of crashing the server.

**Discovery and layout**

- `smartsheet_get_current_user`, `smartsheet_list_home`, `smartsheet_list_personal_root`, `smartsheet_list_workspaces`
- `smartsheet_get_folder`, `smartsheet_get_workspace`
- `smartsheet_search_sheets`, `smartsheet_search_in_sheet`

**Sheets and schema**

- `smartsheet_get_sheet` — general fetch with optional `include`, pagination, row/column filters
- `smartsheet_get_sheet_schema` — metadata and columns without rows (`exclude=rows`)
- `smartsheet_get_sheet_rows_page`, `smartsheet_get_all_sheet_rows` — row reads with paging; `_mcp_truncated` / `_mcp_fetched_row_count` on bulk fetch
- `smartsheet_get_row`

**Column names**

- `smartsheet_resolve_columns` — titles → IDs (`missing` / `ambiguous` duplicate titles)
- `smartsheet_append_row_by_column_names`, `smartsheet_update_row_by_column_names` — write using header names

**Rows and cells**

- `smartsheet_append_row`, `smartsheet_add_rows`, `smartsheet_update_rows`, `smartsheet_update_cells`, `smartsheet_delete_rows`

**Columns**

- `smartsheet_add_column`, `smartsheet_update_column`

## Project layout

```text
.
├── LICENSE
├── README.md
├── pyproject.toml
├── .env.example
├── .github/workflows/ci.yml
└── src/
    └── smartsheet_mcp/
        ├── __init__.py
        ├── __main__.py
        ├── client.py      # HTTP + Smartsheet resultCode handling
        ├── helpers.py     # Pagination + column title resolution
        └── server.py      # FastMCP tools
```

Installable package name: **`smartsheet-mcp`** (pip). Import name: **`smartsheet_mcp`**.

## Development

```bash
pip install -e .
python -c "from smartsheet_mcp.server import mcp; print(mcp.name)"
```

Optional MCP SDK helpers (from the `mcp` package), for example:

```bash
mcp dev src/smartsheet_mcp/server.py
```

## Contributing

Issues and pull requests are welcome. Please keep tokens and `.env` out of git; use `.env.example` as a template only.

## License

This project is licensed under the MIT License; see [LICENSE](./LICENSE).
