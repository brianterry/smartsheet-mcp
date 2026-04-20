"""MCP server exposing Smartsheet REST API tools."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("smartsheet-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0"
