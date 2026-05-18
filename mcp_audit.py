from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

AUDIT_FILE = Path(__file__).resolve().parent / "config" / "mcp_audit.local.jsonl"


def write_mcp_audit(event: str, payload: Dict[str, Any]) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, "payload": payload}
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
