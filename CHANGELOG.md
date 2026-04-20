# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] — 2026-04-20

### Added

- `smartsheet_create_sheet_in_workspace` — `POST /workspaces/{workspaceId}/sheets` (blank grid, custom columns, or `from_template_id` + optional `include`)
- `smartsheet_create_sheet_in_folder` — `POST /folders/{folderId}/sheets`
- `smartsheet_delete_sheet` — `DELETE /sheets/{sheetId}`

## [0.1.1] — 2026-04-20

### Fixed

- `smartsheet_search_sheets` now calls Smartsheet **`GET /search`**. The previous path (`/search/sheets`) returned HTTP 404.

### Changed

- README: clearer Cursor MCP `command` path guidance (avoid `ENOENT` from placeholder paths).

## [0.1.0] — 2026-04-17

### Added

- Initial release: FastMCP stdio server, Smartsheet REST client, helpers for pagination and column-name resolution, GitHub Actions CI, MIT license.

After you publish the repo on GitHub, you can add release/compare links under each version heading.
