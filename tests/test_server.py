"""Smoke test — importing the server builds the FastMCP app, proving the FastMCP 2.0 wiring."""

from __future__ import annotations


def test_server_constructs():
    import apple_mcp.server as srv

    assert srv.mcp is not None
