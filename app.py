from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import requests
from flask import Flask, jsonify, redirect, render_template, request

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
PORTAL_CFG_PATH = CONFIG_DIR / "portal.local.json"

app = Flask(__name__)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_machine_id() -> str:
    env_mid = os.getenv("PORTAL_MACHINE_ID", "").strip()
    if env_mid:
        return env_mid
    candidates = [
        Path.home() / "projects" / "Joormann-Media-Deviceportal" / "var" / "data" / "device.json",
        Path("/home/djanebmb/projects/Joormann-Media-Deviceportal/var/data/device.json"),
        Path("/opt/joormann-media-deviceportal/var/data/device.json"),
    ]
    for candidate in candidates:
        data = _load_json(candidate, {})
        machine_id = str(data.get("machine_id") or "").strip()
        if machine_id:
            return machine_id
    return f"hotword-listener-{uuid.uuid4().hex[:12]}"


def resolve_portal_url(cfg: Dict[str, Any]) -> str:
    env_url = os.getenv("PORTAL_URL", "").strip()
    if env_url:
        return env_url
    existing = str((cfg.get("portal") or {}).get("url") or "").strip()
    if existing:
        return existing
    candidates = [
        Path.home() / "projects" / "Joormann-Media-Deviceportal" / "var" / "data" / "config.json",
        Path("/home/djanebmb/projects/Joormann-Media-Deviceportal/var/data/config.json"),
        Path("/opt/joormann-media-deviceportal/var/data/config.json"),
    ]
    for candidate in candidates:
        data = _load_json(candidate, {})
        for key in ("admin_base_url", "portal_url", "base_url"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
    return ""


def load_config() -> Dict[str, Any]:
    cfg = _load_json(PORTAL_CFG_PATH, {})
    if not isinstance(cfg, dict):
        cfg = {}
    portal = cfg.setdefault("portal", {})
    portal.setdefault("machine_id", resolve_machine_id())
    portal.setdefault("url", resolve_portal_url(cfg))
    cfg.setdefault("listener", {})
    cfg["listener"].setdefault("hotword_service_url", os.getenv("HOTWORD_SERVICE_URL", "http://127.0.0.1:8120"))
    cfg["listener"].setdefault("dispatch_url", os.getenv("HOTWORD_RUNTIME_DISPATCH_URL", "https://joormann-family.de/admin/jarvis/chat?conversation=95"))
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    _save_json(PORTAL_CFG_PATH, cfg)


def _api_headers(api_key: str) -> Dict[str, str]:
    return {"X-API-Key": api_key, "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _portal_sync(cfg: Dict[str, Any]) -> Dict[str, Any]:
    portal = cfg.get("portal") or {}
    portal_url = str(portal.get("url") or "").strip()
    client_id = str(portal.get("client_id") or "").strip()
    api_key = str(portal.get("api_key") or "").strip()
    node_uuid = str(portal.get("node_uuid") or "").strip()
    if not all([portal_url, client_id, api_key, node_uuid]):
        return {"ok": False, "error": "not_registered", "message": "Portal-Credentials fehlen. Erst Link/Register ausführen."}
    payload = {
        "node": {
            "uuid": node_uuid,
            "slug": str(portal.get("node_slug") or ""),
            "machineId": str(portal.get("machine_id") or ""),
            "name": str(portal.get("node_name") or "Hotword Listener"),
            "service": "hotword-listener",
            "baseUrl": str(cfg.get("listener", {}).get("hotword_service_url") or ""),
        }
    }
    try:
        res = requests.post(f"{portal_url.rstrip('/')}/api/jarvis/node/sync", headers=_api_headers(api_key), json=payload, timeout=20)
        return {"ok": res.ok, "status": res.status_code, "response": res.json() if res.headers.get("content-type", "").startswith("application/json") else res.text}
    except Exception as exc:
        return {"ok": False, "error": "portal_unreachable", "message": str(exc)}


def _portal_mcp_sync(cfg: Dict[str, Any]) -> Dict[str, Any]:
    portal = cfg.get("portal") or {}
    portal_url = str(portal.get("url") or "").strip()
    api_key = str(portal.get("api_key") or "").strip()
    node_uuid = str(portal.get("node_uuid") or "").strip()
    if not all([portal_url, api_key, node_uuid]):
        return {"ok": False, "error": "not_registered", "message": "Portal-Credentials fehlen."}
    actions = [
        {
            "actionKey": "hotword.runtime.status",
            "intentKey": "hotword_runtime_status",
            "displayName": "Hotword Runtime Status",
            "description": "Read-only status of hotword runtime",
            "operation": "status",
            "phase": "readonly",
            "risk_level": "low",
            "http_method": "GET",
            "endpoint_template": "/runtime/status",
        },
        {
            "actionKey": "hotword.runtime.test_trigger",
            "intentKey": "hotword_runtime_test_trigger",
            "displayName": "Hotword Runtime Test Trigger",
            "description": "Manual hotword trigger test",
            "operation": "test",
            "phase": "candidate",
            "risk_level": "medium",
            "http_method": "POST",
            "endpoint_template": "/runtime/test-trigger",
        },
    ]
    payload = {"nodeUuid": node_uuid, "source": "mcp", "actions": actions}
    try:
        res = requests.post(f"{portal_url.rstrip('/')}/api/jarvis/node/intents/sync", headers=_api_headers(api_key), json=payload, timeout=20)
        return {"ok": res.ok, "status": res.status_code, "response": res.json() if res.headers.get("content-type", "").startswith("application/json") else res.text}
    except Exception as exc:
        return {"ok": False, "error": "portal_unreachable", "message": str(exc)}


def _hotword_service_health(url: str) -> Dict[str, Any]:
    try:
        res = requests.get(f"{url.rstrip('/')}/health", timeout=5)
        return {"ok": res.ok, "status": res.status_code, "response": res.json() if res.headers.get("content-type", "").startswith("application/json") else res.text}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/")
def index():
    return redirect("/link")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "hotword-listener-manager", "status": "ok"})


@app.get("/info")
def info():
    cfg = load_config()
    return jsonify(
        {
            "ok": True,
            "service": "hotword-listener-manager",
            "version": "0.1.0",
            "endpoints": {
                "link": "/link",
                "portal_status": "/api/portal/status",
                "portal_sync": "/api/portal/sync",
                "runtime_status": "/api/runtime/status",
            },
            "listener": cfg.get("listener") or {},
        }
    )


@app.route("/link", methods=["GET", "POST"])
def link_page():
    cfg = load_config()
    error = ""
    result = None
    if request.method == "POST":
        portal_url = str(request.form.get("portal_url") or "").strip()
        registration_token = str(request.form.get("registration_token") or "").strip()
        node_name = str(request.form.get("node_name") or "Hotword Listener Workstation").strip()
        if not portal_url or not registration_token:
            error = "Portal-URL und Registrierungstoken sind erforderlich."
        else:
            payload = {
                "registrationToken": registration_token,
                "machineId": str(cfg.get("portal", {}).get("machine_id") or resolve_machine_id()),
                "nodeName": node_name,
                "service": "hotword-listener",
                "host": socket.gethostname(),
            }
            try:
                res = requests.post(f"{portal_url.rstrip('/')}/api/jarvis/node/register", json=payload, timeout=20)
                data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                if not res.ok:
                    error = f"Register fehlgeschlagen ({res.status_code}): {data}"
                else:
                    auth = data.get("auth") or {}
                    node = data.get("node") or {}
                    cfg["portal"]["url"] = portal_url
                    cfg["portal"]["client_id"] = str(auth.get("clientId") or cfg["portal"].get("client_id") or "")
                    cfg["portal"]["api_key"] = str(auth.get("apiKey") or cfg["portal"].get("api_key") or "")
                    cfg["portal"]["node_uuid"] = str(node.get("uuid") or cfg["portal"].get("node_uuid") or "")
                    cfg["portal"]["node_slug"] = str(node.get("slug") or cfg["portal"].get("node_slug") or "")
                    cfg["portal"]["node_name"] = node_name
                    save_config(cfg)
                    sync_result = _portal_sync(cfg)
                    mcp_result = _portal_mcp_sync(cfg)
                    result = {"register": data, "sync": sync_result, "mcp": mcp_result}
            except Exception as exc:
                error = f"Portal nicht erreichbar: {exc}"

    portal = cfg.get("portal") or {}
    portal_status = {
        "registered": bool(portal.get("client_id") and portal.get("api_key")),
        "portal_url": portal.get("url"),
        "node_uuid": portal.get("node_uuid"),
        "node_slug": portal.get("node_slug"),
        "machine_id": portal.get("machine_id"),
        "client_id": portal.get("client_id"),
        "mac_address": portal.get("mac_address"),
        "outbound_api_key_masked": ("***" + str(portal.get("api_key") or "")[-4:]) if portal.get("api_key") else None,
        "admin_api_key_configured": bool(portal.get("admin_api_key")),
    }
    form = {
        "portal_url": str(portal_status.get("portal_url") or ""),
        "registration_token": "",
        "node_name": str(portal.get("node_name") or "Hotword-Listener Workstation"),
    }
    listener = cfg.get("listener") or {}
    hotword_health = _hotword_service_health(str(listener.get("hotword_service_url") or "http://127.0.0.1:8120"))
    return render_template(
        "link.html",
        error=error,
        result=result,
        form=form,
        portal_status=portal_status,
        listener=listener,
        hotword_health=hotword_health,
    )


@app.get("/api/portal/status")
def api_portal_status():
    cfg = load_config()
    portal = cfg.get("portal") or {}
    return jsonify({
        "ok": True,
        "registered": bool(portal.get("client_id") and portal.get("api_key")),
        "portal_url": portal.get("url"),
        "node_uuid": portal.get("node_uuid"),
        "node_slug": portal.get("node_slug"),
        "machine_id": portal.get("machine_id"),
        "client_id": portal.get("client_id"),
    })


@app.post("/api/portal/sync")
def api_portal_sync():
    cfg = load_config()
    node_sync = _portal_sync(cfg)
    mcp_sync = _portal_mcp_sync(cfg)
    ok = bool(node_sync.get("ok") and mcp_sync.get("ok"))
    return jsonify({"ok": ok, "node_ok": bool(node_sync.get("ok")), "node_sync_ok": bool(node_sync.get("ok")), "mcp_ok": bool(mcp_sync.get("ok")), "node_sync": node_sync, "mcp_intents_sync": mcp_sync}), (200 if ok else 502)


@app.post("/api/portal/relink")
def api_portal_relink():
    cfg = load_config()
    body = request.get_json(silent=True) or {}
    portal_url = str(body.get("portal_url") or cfg.get("portal", {}).get("url") or "").strip()
    payload = {
        "uuid": str(body.get("uuid") or "").strip(),
        "slug": str(body.get("slug") or "").strip(),
        "clientId": str(body.get("client_id") or "").strip(),
        "macAddress": str(body.get("mac_address") or "").strip(),
        "machineId": str(cfg.get("portal", {}).get("machine_id") or "").strip(),
    }
    if not portal_url:
        return jsonify({"ok": False, "error": "portal_url_missing"}), 400
    try:
        res = requests.post(f"{portal_url.rstrip('/')}/api/jarvis/node/relink", json=payload, timeout=20)
        data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {"raw": res.text}
        if res.ok:
            auth = data.get("auth") or {}
            node = data.get("node") or {}
            cfg["portal"]["url"] = portal_url
            cfg["portal"]["client_id"] = str(auth.get("clientId") or cfg["portal"].get("client_id") or "")
            cfg["portal"]["api_key"] = str(auth.get("apiKey") or cfg["portal"].get("api_key") or "")
            cfg["portal"]["node_uuid"] = str(node.get("uuid") or cfg["portal"].get("node_uuid") or "")
            cfg["portal"]["node_slug"] = str(node.get("slug") or cfg["portal"].get("node_slug") or "")
            save_config(cfg)
        return jsonify({"ok": res.ok, "status": res.status_code, "response": data}), (200 if res.ok else 502)
    except Exception as exc:
        return jsonify({"ok": False, "error": "portal_unreachable", "message": str(exc)}), 502


@app.get("/api/runtime/status")
def api_runtime_status():
    cfg = load_config()
    base = str(cfg.get("listener", {}).get("hotword_service_url") or "http://127.0.0.1:8120")
    try:
        res = requests.get(f"{base.rstrip('/')}/runtime/status", timeout=10)
        return jsonify({"ok": res.ok, "status": res.status_code, "response": res.json()}), (200 if res.ok else 502)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


@app.post("/api/runtime/<action>")
def api_runtime_action(action: str):
    if action not in {"start", "stop", "reload-hotwords", "test-trigger"}:
        return jsonify({"ok": False, "error": "unsupported_action"}), 400
    cfg = load_config()
    base = str(cfg.get("listener", {}).get("hotword_service_url") or "http://127.0.0.1:8120")
    try:
        res = requests.post(f"{base.rstrip('/')}/runtime/{action}", timeout=15)
        data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {"raw": res.text}
        return jsonify({"ok": res.ok, "status": res.status_code, "response": data}), (200 if res.ok else 502)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5103"))
    app.run(host="0.0.0.0", port=port)
