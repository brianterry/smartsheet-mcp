"""Shared logic for sheet pagination and column name resolution."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import Any


def _norm_title(title: str) -> str:
    return title.strip().casefold()


def build_title_to_column_id(
    columns: Iterable[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, list[int]]]:
    """Map normalized title -> a representative columnId; ambiguous maps title -> all IDs when duplicates."""
    buckets: dict[str, list[int]] = defaultdict(list)
    for col in columns:
        cid = col.get("id")
        title = col.get("title")
        if cid is None or title is None or not isinstance(title, str):
            continue
        key = _norm_title(title)
        if not key:
            continue
        buckets[key].append(int(cid))

    title_to_id: dict[str, int] = {}
    ambiguous: dict[str, list[int]] = {}
    for key, ids in buckets.items():
        uniq = sorted(set(ids))
        if len(uniq) > 1:
            ambiguous[key] = uniq
        title_to_id[key] = uniq[0]
    return title_to_id, ambiguous


def resolve_column_names(
    columns: Iterable[dict[str, Any]],
    names: list[str],
) -> tuple[dict[str, int], list[str], dict[str, list[int]]]:
    """resolved (requested name -> columnId), missing requested names, ambiguous (requested name -> ids)."""
    title_map, amb_keys = build_title_to_column_id(columns)
    resolved: dict[str, int] = {}
    missing: list[str] = []
    ambiguous: dict[str, list[int]] = {}
    for raw in names:
        key = _norm_title(raw)
        if not key:
            missing.append(raw)
            continue
        if key in amb_keys:
            ambiguous[raw] = amb_keys[key]
            continue
        cid = title_map.get(key)
        if cid is None:
            missing.append(raw)
        else:
            resolved[raw] = cid
    return resolved, missing, ambiguous


def cells_from_name_values(
    columns: Iterable[dict[str, Any]],
    values: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str], dict[str, list[int]]]:
    """Build Smartsheet cells from title->value. missing = unknown titles; ambiguous = duplicate titles in sheet."""
    title_map, amb_keys = build_title_to_column_id(columns)
    cells: list[dict[str, Any]] = []
    missing: list[str] = []
    ambiguous: dict[str, list[int]] = {}
    for name, val in values.items():
        key = _norm_title(name)
        if not key:
            missing.append(name)
            continue
        if key in amb_keys:
            ambiguous[name] = amb_keys[key]
            continue
        cid = title_map.get(key)
        if cid is None:
            missing.append(name)
        else:
            cells.append({"columnId": cid, "value": val})
    return cells, missing, ambiguous


def fetch_all_sheet_rows(
    *,
    get_sheet: Callable[[dict[str, Any]], dict[str, Any]],
    page_size: int = 500,
    max_rows: int = 10_000,
) -> dict[str, Any]:
    """Fetch all rows via paged GET /sheets/{id}. get_sheet(params) -> full JSON dict."""
    if max_rows < 1:
        return {"error": "max_rows must be at least 1"}

    first: dict[str, Any] | None = None
    all_rows: list[Any] = []
    page = 1
    total: int | None = None
    last_batch_len = 0

    while len(all_rows) < max_rows:
        batch_cap = min(page_size, max_rows - len(all_rows))
        data = get_sheet(
            {
                "include": "rows",
                "pageSize": batch_cap,
                "page": page,
            },
        )
        if first is None:
            first = data
            tr = data.get("totalRowCount")
            if tr is not None:
                total = int(tr)
        rows = data.get("rows") or []
        last_batch_len = len(rows)
        all_rows.extend(rows)
        if not rows:
            break
        if total is not None and len(all_rows) >= total:
            break
        if last_batch_len < batch_cap:
            break
        page += 1

    if first is None:
        return {"error": "No data returned from Smartsheet"}

    out = dict(first)
    out["rows"] = all_rows
    truncated = False
    if len(all_rows) >= max_rows and last_batch_len == batch_cap:
        truncated = True
    if total is not None and len(all_rows) < total:
        truncated = True
    out["_mcp_truncated"] = truncated
    out["_mcp_fetched_row_count"] = len(all_rows)
    return out


def build_create_sheet_body(
    name: str,
    columns: list[dict[str, Any]] | None,
    *,
    from_template_id: str | None,
) -> dict[str, Any]:
    """Build JSON body for POST /workspaces/{id}/sheets or POST /folders/{id}/sheets."""
    if from_template_id:
        return {"name": name, "fromId": int(from_template_id)}
    if columns:
        return {"name": name, "columns": columns}
    return {
        "name": name,
        "columns": [{"title": "Primary", "type": "TEXT_NUMBER", "primary": True}],
    }


def group_cell_updates(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn flat change list into PUT /rows row objects."""
    by_row: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for ch in changes:
        rid = ch.get("row_id", ch.get("rowId"))
        cid = ch.get("column_id", ch.get("columnId"))
        if rid is None or cid is None:
            raise ValueError("Each change needs row_id, column_id, and value")
        val = ch.get("value")
        by_row[int(rid)].append({"columnId": int(cid), "value": val})
    return [{"id": rid, "cells": cells} for rid, cells in sorted(by_row.items(), key=lambda x: x[0])]
