"""FastMCP server: Smartsheet API tools (stdio by default)."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from smartsheet_mcp.client import SmartsheetAPIError, get_client
from smartsheet_mcp import helpers

mcp = FastMCP(
    "smartsheet",
    instructions=(
        "Tools call the Smartsheet REST API (v2). "
        "Set SMARTSHEET_ACCESS_TOKEN in the server environment. "
        "Optional SMARTSHEET_BASE_URL (default https://api.smartsheet.com/2.0)."
    ),
    json_response=True,
)


def _tool_error(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, SmartsheetAPIError):
        out: dict[str, Any] = {"error": str(exc)}
        if exc.status_code is not None:
            out["http_status"] = exc.status_code
        if exc.payload is not None:
            out["smartsheet"] = exc.payload
        return out
    if isinstance(exc, httpx.HTTPError):
        return {"error": f"HTTP error: {exc}"}
    return {"error": str(exc)}


def _run(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — surface to model as JSON
        return _tool_error(exc)


@mcp.tool()
def smartsheet_get_current_user() -> dict[str, Any]:
    """Return the authenticated user profile (GET /users/me)."""
    return _run(lambda: get_client().get("/users/me"))


@mcp.tool()
def smartsheet_list_home() -> dict[str, Any]:
    """List root home contents (GET /home). Prefer list_personal_root and list_workspaces for newer integrations."""
    return _run(lambda: get_client().get("/home"))


@mcp.tool()
def smartsheet_list_personal_root() -> dict[str, Any]:
    """List nested Home objects shared to the user (GET /folders/personal)."""
    return _run(lambda: get_client().get("/folders/personal"))


@mcp.tool()
def smartsheet_list_workspaces() -> dict[str, Any]:
    """List workspaces visible to the user (GET /workspaces)."""
    return _run(lambda: get_client().get("/workspaces"))


@mcp.tool()
def smartsheet_get_sheet(
    sheet_id: str,
    *,
    include: str | None = None,
    page_size: int | None = None,
    page: int | None = None,
    row_ids: str | None = None,
    column_ids: str | None = None,
) -> dict[str, Any]:
    """Fetch a sheet. Use include (comma-separated Smartsheet flags) to add rows, attachments, etc.

    Args:
        sheet_id: Sheet ID.
        include: e.g. "rows,columnType,discussions,attachments".
        page_size: Pagination page size when rows are included.
        page: 1-based page index when rows are included.
        row_ids: Comma-separated row IDs to narrow row data.
        column_ids: Comma-separated column IDs to narrow cell data.
    """
    params: dict[str, Any] = {}
    if include:
        params["include"] = include
    if page_size is not None:
        params["pageSize"] = page_size
    if page is not None:
        params["page"] = page
    if row_ids:
        params["rowIds"] = row_ids
    if column_ids:
        params["columnIds"] = column_ids
    return _run(lambda: get_client().get(f"/sheets/{sheet_id}", params=params or None))


@mcp.tool()
def smartsheet_get_sheet_schema(
    sheet_id: str,
    *,
    include_column_types: bool = True,
) -> dict[str, Any]:
    """Fetch sheet metadata and columns without row data (GET /sheets/{id} with exclude=rows).

    Args:
        sheet_id: Sheet ID.
        include_column_types: When true, add include=columnType for detailed column typing.
    """
    params: dict[str, Any] = {"exclude": "rows"}
    if include_column_types:
        params["include"] = "columnType"
    return _run(lambda: get_client().get(f"/sheets/{sheet_id}", params=params))


@mcp.tool()
def smartsheet_get_sheet_rows_page(
    sheet_id: str,
    *,
    page: int = 1,
    page_size: int = 500,
    column_ids: str | None = None,
) -> dict[str, Any]:
    """Fetch one page of row data (GET /sheets/{id} with include=rows and page/pageSize)."""
    params: dict[str, Any] = {"include": "rows", "page": page, "pageSize": page_size}
    if column_ids:
        params["columnIds"] = column_ids
    return _run(lambda: get_client().get(f"/sheets/{sheet_id}", params=params))


@mcp.tool()
def smartsheet_get_all_sheet_rows(
    sheet_id: str,
    *,
    page_size: int = 500,
    max_rows: int = 10_000,
) -> dict[str, Any]:
    """Fetch rows across pages until the sheet ends or max_rows is reached.

    Response includes _mcp_truncated (more rows existed but were not fetched) and
    _mcp_fetched_row_count. Lower max_rows for very large sheets to control token size.
    """
    return _run(
        lambda: helpers.fetch_all_sheet_rows(
            get_sheet=lambda p: get_client().get(f"/sheets/{sheet_id}", params=p),
            page_size=page_size,
            max_rows=max_rows,
        ),
    )


@mcp.tool()
def smartsheet_append_row(sheet_id: str, cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Append one row to the bottom of the sheet (POST /rows with a single toBottom row).

    Each cell object should include columnId and value (per Smartsheet Cell JSON).
    """
    row = {"toBottom": True, "cells": cells}
    return _run(lambda: get_client().post(f"/sheets/{sheet_id}/rows", json_body=[row]))


@mcp.tool()
def smartsheet_update_cells(sheet_id: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
    """Update many cells across one or more rows (PUT /rows).

    Each change is a dict with row_id, column_id, and value (camelCase rowId/columnId also accepted).
    """
    def _go() -> dict[str, Any]:
        rows_payload = helpers.group_cell_updates(changes)
        return get_client().put(f"/sheets/{sheet_id}/rows", json_body=rows_payload)

    return _run(_go)


@mcp.tool()
def smartsheet_search_in_sheet(sheet_id: str, query: str) -> dict[str, Any]:
    """Search for text inside a specific sheet (GET /search/sheets/{sheetId})."""
    return _run(lambda: get_client().get(f"/search/sheets/{sheet_id}", params={"query": query}))


@mcp.tool()
def smartsheet_resolve_columns(sheet_id: str, column_names: list[str]) -> dict[str, Any]:
    """Map column titles to column IDs for a sheet (case-insensitive, trimmed).

    Returns resolved, missing, and ambiguous (duplicate titles in the sheet).
    """
    def _go() -> dict[str, Any]:
        schema = get_client().get(
            f"/sheets/{sheet_id}",
            params={"exclude": "rows", "include": "columnType"},
        )
        cols = schema.get("columns")
        if not isinstance(cols, list):
            return {"error": "Sheet schema response missing columns", "schema": schema}
        resolved, missing, ambiguous = helpers.resolve_column_names(cols, column_names)
        return {
            "resolved": resolved,
            "missing": missing,
            "ambiguous": ambiguous,
        }

    return _run(_go)


@mcp.tool()
def smartsheet_append_row_by_column_names(
    sheet_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Append one bottom row using column titles as keys in values (case-insensitive).

    Unknown or ambiguous column titles return an error object without calling add-rows.
    """
    def _go() -> dict[str, Any]:
        if not values:
            return {"error": "values must contain at least one column name entry"}
        schema = get_client().get(
            f"/sheets/{sheet_id}",
            params={"exclude": "rows", "include": "columnType"},
        )
        cols = schema.get("columns")
        if not isinstance(cols, list):
            return {"error": "Sheet schema response missing columns", "schema": schema}
        cells, missing, ambiguous = helpers.cells_from_name_values(cols, values)
        if missing or ambiguous:
            return {
                "error": "Unresolved column names; fix and retry.",
                "missing": missing,
                "ambiguous": ambiguous,
            }
        row = {"toBottom": True, "cells": cells}
        return get_client().post(f"/sheets/{sheet_id}/rows", json_body=[row])

    return _run(_go)


@mcp.tool()
def smartsheet_update_row_by_column_names(
    sheet_id: str,
    row_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update one row using column titles as keys in values (case-insensitive)."""
    def _go() -> dict[str, Any]:
        if not values:
            return {"error": "values must contain at least one column name entry"}
        schema = get_client().get(
            f"/sheets/{sheet_id}",
            params={"exclude": "rows", "include": "columnType"},
        )
        cols = schema.get("columns")
        if not isinstance(cols, list):
            return {"error": "Sheet schema response missing columns", "schema": schema}
        cells, missing, ambiguous = helpers.cells_from_name_values(cols, values)
        if missing or ambiguous:
            return {
                "error": "Unresolved column names; fix and retry.",
                "missing": missing,
                "ambiguous": ambiguous,
            }
        return get_client().put(
            f"/sheets/{sheet_id}/rows",
            json_body=[{"id": int(row_id), "cells": cells}],
        )

    return _run(_go)


@mcp.tool()
def smartsheet_search_sheets(query: str) -> dict[str, Any]:
    """Search sheets the user can access (GET /search/sheets)."""
    return _run(lambda: get_client().get("/search/sheets", params={"query": query}))


@mcp.tool()
def smartsheet_get_folder(folder_id: str) -> dict[str, Any]:
    """Get a folder including child folders and sheets (GET /folders/{folderId})."""
    return _run(lambda: get_client().get(f"/folders/{folder_id}"))


@mcp.tool()
def smartsheet_get_workspace(workspace_id: str) -> dict[str, Any]:
    """Get a workspace including top-level folders and sheets (GET /workspaces/{workspaceId})."""
    return _run(lambda: get_client().get(f"/workspaces/{workspace_id}"))


@mcp.tool()
def smartsheet_add_rows(sheet_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Append or insert rows (POST /sheets/{sheetId}/rows). Each row follows Smartsheet Row JSON (cells, toBottom, etc.)."""
    return _run(lambda: get_client().post(f"/sheets/{sheet_id}/rows", json_body=rows))


@mcp.tool()
def smartsheet_update_rows(sheet_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Update existing rows (PUT /sheets/{sheetId}/rows). Each row must include id and cells or other updatable fields."""
    return _run(lambda: get_client().put(f"/sheets/{sheet_id}/rows", json_body=rows))


@mcp.tool()
def smartsheet_delete_rows(sheet_id: str, row_ids: list[int]) -> dict[str, Any]:
    """Delete rows by ID (DELETE /sheets/{sheetId}/rows with ids query)."""
    ids = ",".join(str(i) for i in row_ids)
    return _run(lambda: get_client().delete(f"/sheets/{sheet_id}/rows", params={"ids": ids}))


@mcp.tool()
def smartsheet_get_row(sheet_id: str, row_id: str, include: str | None = None) -> dict[str, Any]:
    """Fetch a single row (GET /sheets/{sheetId}/rows/{rowId})."""
    params = {"include": include} if include else None
    return _run(lambda: get_client().get(f"/sheets/{sheet_id}/rows/{row_id}", params=params))


@mcp.tool()
def smartsheet_add_column(sheet_id: str, column: dict[str, Any]) -> dict[str, Any]:
    """Add one column (POST /sheets/{sheetId}/columns). Column must include title and type (PRIMARY, TEXT_NUMBER, etc.)."""
    return _run(lambda: get_client().post(f"/sheets/{sheet_id}/columns", json_body=column))


@mcp.tool()
def smartsheet_update_column(sheet_id: str, column_id: str, column: dict[str, Any]) -> dict[str, Any]:
    """Update column definition (PUT /sheets/{sheetId}/columns/{columnId})."""
    return _run(lambda: get_client().put(f"/sheets/{sheet_id}/columns/{column_id}", json_body=column))


def main() -> None:
    if not os.environ.get("SMARTSHEET_ACCESS_TOKEN"):
        print(
            "smartsheet-mcp: set SMARTSHEET_ACCESS_TOKEN in the MCP server environment.",
            file=sys.stderr,
        )
        sys.exit(1)
    mcp.run()


if __name__ == "__main__":
    main()
