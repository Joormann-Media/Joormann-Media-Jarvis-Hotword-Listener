from __future__ import annotations

from mcp_registry import load_mcp_actions


def registry_status() -> dict:
    actions = load_mcp_actions()
    enabled_readonly = [a for a in actions if a.get("enabled") and a.get("phase") == "readonly" and a.get("http_method") == "GET"]
    return {"ok": True, "total_actions": len(actions), "exported_readonly_actions": len(enabled_readonly)}
