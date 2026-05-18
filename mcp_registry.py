from __future__ import annotations

from typing import Any, Dict, List


def load_mcp_actions() -> List[Dict[str, Any]]:
    return [
        {
            "id": "hotword.runtime.status",
            "tool_name": "hotword.runtime.status",
            "display_name": "Hotword Runtime Status",
            "description": "Read-only status of hotword runtime",
            "http_method": "GET",
            "endpoint_template": "/runtime/status",
            "enabled": True,
            "phase": "readonly",
            "risk_level": "low",
        },
        {
            "id": "hotword.runtime.test_trigger",
            "tool_name": "hotword.runtime.test_trigger",
            "display_name": "Hotword Runtime Test Trigger",
            "description": "Manual runtime trigger test",
            "http_method": "POST",
            "endpoint_template": "/runtime/test-trigger",
            "enabled": False,
            "phase": "candidate",
            "risk_level": "medium",
        },
    ]
