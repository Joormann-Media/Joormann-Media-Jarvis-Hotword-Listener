import json
from datetime import datetime, timezone
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, File, Form, UploadFile, status, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.routing import APIRoute

from .config import settings, PROJECT_ROOT
from .manager import build_model, detect_hotword, get_model_status
from .runtime import (
    configure_runtime_audio_input,
    runtime_audio_probe,
    configure_runtime_audio_tuning,
    configure_runtime_listener,
    get_runtime_audio_devices,
    get_runtime_audio_tuning,
    get_runtime_config,
    get_runtime_status,
    reload_runtime_hotwords,
    start_runtime_listener,
    stop_runtime_listener,
    test_runtime_trigger,
)
from .schemas import (
    DetectRequest,
    DetectResponse,
    DetectUploadResponse,
    ErrorResponse,
    HealthResponse,
    HotwordCreateRequest,
    HotwordCreateResponse,
    HotwordDeleteResponse,
    HotwordDetailResponse,
    HotwordBulkDeleteResponse,
    HotwordListResponse,
    HotwordModelUploadResponse,
    HotwordUpdateRequest,
    HotwordUpdateResponse,
    ModelBuildResponse,
    ModelStatusResponse,
    RuntimeAudioDevicesResponse,
    RuntimeAudioInputRequest,
    RuntimeAudioProbeRequest,
    RuntimeAudioProbeResponse,
    RuntimeAudioTuningRequest,
    RuntimeAudioTuningResponse,
    RuntimeConfigResponse,
    RuntimeListenerConfigRequest,
    RuntimeControlResponse,
    RuntimeStatusResponse,
    RuntimeTriggerResponse,
    SampleListResponse,
    SampleUploadResponse,
    SpeakerListReferenceResponse,
)
from .storage import (
    create_hotword,
    delete_all_hotwords,
    delete_hotword,
    get_hotword,
    list_available_speakers,
    list_hotwords,
    list_samples,
    save_model_file,
    save_test_upload,
    save_upload_file,
    update_hotword,
)


router = APIRouter()
_runtime_trainer_token: str | None = None
_status_last_error: dict[str, object] | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_error_response(detail: str, error: str, status_code: int) -> JSONResponse:
    payload = ErrorResponse(
        service=settings.service_name,
        error=error,
        detail=detail,
        timestamp=utc_now(),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _value_or_demo(value: object, fallback: str = "DEMO") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _build_family_url(path: str) -> str:
    return settings.family_panel_url.rstrip("/") + "/" + path.lstrip("/")


async def _resolve_trainer_token() -> tuple[str | None, dict[str, object] | None]:
    global _runtime_trainer_token

    if settings.family_panel_trainer_token:
        return settings.family_panel_trainer_token, None
    if _runtime_trainer_token:
        return _runtime_trainer_token, None
    if not settings.family_panel_sync_token:
        return None, {
            "ok": False,
            "error": "trainer_token_missing",
            "detail": "Auto-token handshake failed: FAMILY_PANEL_SYNC_TOKEN/PORTAL_REGISTRY_PUSH_TOKEN missing.",
        }

    headers = {"X-Portal-Sync-Token": settings.family_panel_sync_token}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                _build_family_url(settings.family_panel_trainer_auto_token_path),
                headers=headers,
            )
    except httpx.HTTPError as exc:
        return None, {
            "ok": False,
            "error": "trainer_token_fetch_failed",
            "detail": f"Auto-token handshake failed: {exc}",
        }

    try:
        payload = response.json()
    except ValueError:
        payload = {"ok": False, "error": "invalid_family_response"}

    if response.status_code >= 400:
        return None, payload if isinstance(payload, dict) else {
            "ok": False,
            "error": "trainer_token_fetch_failed",
            "detail": "Auto-token endpoint returned an error",
        }

    if not isinstance(payload, dict):
        return None, {
            "ok": False,
            "error": "trainer_token_fetch_failed",
            "detail": "Auto-token endpoint returned invalid payload",
        }

    token = str(payload.get("trainer_token", "")).strip()
    if not token:
        return None, {
            "ok": False,
            "error": "trainer_token_fetch_failed",
            "detail": "Auto-token endpoint returned empty token",
        }

    _runtime_trainer_token = token
    return token, None


def _set_status_error(source: str, detail: str) -> None:
    global _status_last_error
    _status_last_error = {
        "source": source,
        "detail": detail,
        "timestamp": utc_now().isoformat(),
    }


def _guess_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        return None
    return None


def _base_url_for_port(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _port_from_url(url: str, fallback: int) -> int:
    parsed = urlparse(url)
    if parsed.port:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    if parsed.scheme == "http":
        return 80
    return fallback


async def _check_url(url: str, timeout: float = 2.5) -> dict[str, object]:
    started = datetime.now(tz=timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
        duration_ms = round((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000, 2)
        return {
            "url": url,
            "ok": response.status_code < 400,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
    except httpx.HTTPError as exc:
        return {
            "url": url,
            "ok": False,
            "status_code": None,
            "duration_ms": None,
            "error": str(exc),
        }


def _run_update_manager(mode: str) -> dict[str, object]:
    script = PROJECT_ROOT / "scripts" / "update_manager.sh"
    if not script.exists():
        return {
            "ok": False,
            "code": "script_missing",
            "message": f"Update script not found: {script}",
            "log": "",
        }

    if mode not in {"status", "apply"}:
        return {
            "ok": False,
            "code": "invalid_mode",
            "message": f"Invalid mode: {mode}",
            "log": "",
        }

    try:
        result = subprocess.run(
            ["bash", str(script), mode],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300 if mode == "apply" else 30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "code": "update_exec_failed",
            "message": str(exc),
            "log": "",
        }

    output = (result.stdout or "").strip()
    if not output:
        return {
            "ok": False,
            "code": "empty_update_response",
            "message": "Update script returned no output",
            "log": result.stderr or "",
        }

    try:
        payload = json.loads(output)
    except ValueError:
        return {
            "ok": False,
            "code": "invalid_update_response",
            "message": "Update script returned invalid JSON",
            "raw": output,
        }

    if not isinstance(payload, dict):
        return {
            "ok": False,
            "code": "invalid_update_response",
            "message": "Update script returned non-object payload",
            "raw": output,
        }
    return payload


@router.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "status": "ok",
        "message": "Hotword service is alive",
    }


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        service=settings.service_name,
        status="healthy",
        timestamp=utc_now(),
        environment=settings.jarvis_env,
    )


@router.get("/status")
async def status_overview(request: Request) -> JSONResponse:
    lan_ip = _guess_lan_ip()
    hotword_port = settings.service_port
    trainer_port = _port_from_url(settings.hotword_trainer_url, 8117)
    speaker_port = _port_from_url(settings.speaker_id_service_url, 8113)

    localhost_links = {
        "hotword_ui": _base_url_for_port("localhost", hotword_port) + "/ui",
        "assistant_ui": _base_url_for_port("localhost", hotword_port) + "/assistant",
        "hotword_status": _base_url_for_port("localhost", hotword_port) + "/status",
        "runtime_status": _base_url_for_port("localhost", hotword_port) + "/runtime/status",
        "speaker_ui": _base_url_for_port("localhost", speaker_port) + "/ui",
        "trainer_health": _base_url_for_port("localhost", trainer_port) + "/health",
    }
    lan_links = (
        {
            "hotword_ui": _base_url_for_port(lan_ip, hotword_port) + "/ui",
            "assistant_ui": _base_url_for_port(lan_ip, hotword_port) + "/assistant",
            "hotword_status": _base_url_for_port(lan_ip, hotword_port) + "/status",
            "runtime_status": _base_url_for_port(lan_ip, hotword_port) + "/runtime/status",
            "speaker_ui": _base_url_for_port(lan_ip, speaker_port) + "/ui",
            "trainer_health": _base_url_for_port(lan_ip, trainer_port) + "/health",
        }
        if lan_ip
        else {}
    )

    endpoint_checks = [
        await _check_url(localhost_links["hotword_status"]),
        await _check_url(localhost_links["runtime_status"]),
        await _check_url(localhost_links["hotword_ui"]),
        await _check_url(localhost_links["assistant_ui"]),
        await _check_url(localhost_links["speaker_ui"]),
        await _check_url(localhost_links["trainer_health"]),
    ]

    update_info = _run_update_manager("status")
    if not bool(update_info.get("ok", False)):
        _set_status_error("update_status", str(update_info.get("message", "unknown error")))

    route_catalog = []
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        route_catalog.append(
            {
                "path": route.path,
                "methods": sorted(list(route.methods - {"HEAD", "OPTIONS"})),
                "name": route.name,
            }
        )

    runtime_payload = get_runtime_status().model_dump(mode="json")
    payload = {
        "service": settings.service_name,
        "status": "ok",
        "version": settings.service_version,
        "timestamp": utc_now().isoformat(),
        "environment": settings.jarvis_env,
        "request_host": request.headers.get("host", ""),
        "ports": {
            "hotword_service": hotword_port,
            "hotword_trainer": trainer_port,
            "speaker_id_service": speaker_port,
        },
        "links": {
            "localhost": localhost_links,
            "lan": lan_links,
        },
        "runtime": runtime_payload,
        "update": update_info,
        "last_error": _status_last_error,
        "actions": {
            "runtime_start": "/status/actions/runtime/start",
            "runtime_stop": "/status/actions/runtime/stop",
            "runtime_reload_hotwords": "/status/actions/runtime/reload",
            "runtime_test_trigger": "/status/actions/runtime/test-trigger",
            "lab_update_status": "/status/actions/lab-update?mode=status",
            "lab_update_apply": "/status/actions/lab-update?mode=apply",
        },
        "endpoint_feedback": endpoint_checks,
        "routes": {
            "count": len(route_catalog),
            "items": route_catalog,
        },
    }
    return JSONResponse(status_code=200, content=payload)


@router.post("/status/actions/runtime/{action}")
def status_runtime_action(action: str) -> JSONResponse:
    action_name = action.strip().lower()
    action_map = {
        "start": start_runtime_listener,
        "stop": stop_runtime_listener,
        "reload": reload_runtime_hotwords,
        "test-trigger": test_runtime_trigger,
    }
    handler = action_map.get(action_name)
    if handler is None:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "invalid_action",
                "detail": f"Unknown runtime action '{action_name}'",
                "available_actions": sorted(action_map.keys()),
            },
        )
    try:
        result = handler()
        payload = result.model_dump(mode="json")
    except Exception as exc:  # pragma: no cover - defensive runtime endpoint
        _set_status_error("runtime_action", str(exc))
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "runtime_action_failed", "detail": str(exc)},
        )
    return JSONResponse(
        status_code=200,
        content={"ok": True, "action": action_name, "feedback": payload},
    )


@router.post("/status/actions/lab-update")
def status_lab_update(mode: str = "status") -> JSONResponse:
    payload = _run_update_manager(mode.strip().lower())
    ok = bool(payload.get("ok", False))
    if not ok:
        _set_status_error("lab_update", str(payload.get("message", "unknown update error")))
    return JSONResponse(
        status_code=200 if ok else 500,
        content={
            "ok": ok,
            "mode": mode,
            "feedback": payload,
        },
    )


@router.get("/speakers", response_model=SpeakerListReferenceResponse)
def speakers() -> SpeakerListReferenceResponse:
    return SpeakerListReferenceResponse(
        service=settings.service_name,
        status="ok",
        speakers=list_available_speakers(),
    )


@router.get("/hotwords", response_model=HotwordListResponse)
def hotwords() -> HotwordListResponse:
    return HotwordListResponse(
        service=settings.service_name,
        status="ok",
        hotwords=list_hotwords(),
    )


@router.post("/hotwords", response_model=HotwordCreateResponse)
def create_hotword_route(request: HotwordCreateRequest) -> HotwordCreateResponse:
    try:
        hotword = create_hotword(request)
    except ValueError as exc:
        return build_error_response(str(exc), "hotword_exists", status.HTTP_409_CONFLICT)

    return HotwordCreateResponse(
        service=settings.service_name,
        status="ok",
        hotword=hotword,
        message="Hotword created successfully",
    )


@router.get("/hotwords/{hotword_id}", response_model=HotwordDetailResponse)
def hotword_detail(hotword_id: str) -> HotwordDetailResponse:
    hotword = get_hotword(hotword_id)
    if not hotword:
        return build_error_response("hotword not found", "hotword_not_found", status.HTTP_404_NOT_FOUND)

    return HotwordDetailResponse(
        service=settings.service_name,
        status="ok",
        hotword=hotword,
        samples=list_samples(hotword_id),
    )


@router.patch("/hotwords/{hotword_id}", response_model=HotwordUpdateResponse)
def hotword_update(hotword_id: str, request: HotwordUpdateRequest) -> HotwordUpdateResponse:
    try:
        hotword = update_hotword(hotword_id, request)
    except ValueError:
        return build_error_response("hotword not found", "hotword_not_found", status.HTTP_404_NOT_FOUND)

    return HotwordUpdateResponse(
        service=settings.service_name,
        status="ok",
        hotword=hotword,
        message="Hotword updated successfully",
    )


@router.delete("/hotwords/{hotword_id}", response_model=HotwordDeleteResponse)
def hotword_delete(hotword_id: str) -> HotwordDeleteResponse:
    deleted = delete_hotword(hotword_id)
    if not deleted:
        return build_error_response("hotword not found", "hotword_not_found", status.HTTP_404_NOT_FOUND)

    return HotwordDeleteResponse(
        service=settings.service_name,
        status="ok",
        hotword_id=hotword_id,
        message="Hotword deleted successfully",
    )


@router.delete("/hotwords", response_model=HotwordBulkDeleteResponse)
def hotwords_delete_all() -> HotwordBulkDeleteResponse:
    deleted_ids = delete_all_hotwords()
    return HotwordBulkDeleteResponse(
        service=settings.service_name,
        status="ok",
        deleted_hotword_ids=deleted_ids,
        message=f"Deleted {len(deleted_ids)} hotword(s)",
    )


@router.get("/hotwords/{hotword_id}/samples", response_model=SampleListResponse)
def hotword_samples(hotword_id: str) -> SampleListResponse:
    hotword = get_hotword(hotword_id)
    if not hotword:
        return build_error_response("hotword not found", "hotword_not_found", status.HTTP_404_NOT_FOUND)

    return SampleListResponse(
        service=settings.service_name,
        status="ok",
        hotword_id=hotword_id,
        samples=list_samples(hotword_id),
    )


@router.post("/hotwords/{hotword_id}/samples/upload", response_model=SampleUploadResponse)
async def upload_hotword_sample(hotword_id: str, file: UploadFile = File(...)) -> SampleUploadResponse:
    hotword = get_hotword(hotword_id)
    if not hotword:
        return build_error_response("hotword not found", "hotword_not_found", status.HTTP_404_NOT_FOUND)

    sample = await save_upload_file(hotword_id, file, prefix="upload")
    return SampleUploadResponse(
        service=settings.service_name,
        status="ok",
        hotword_id=hotword_id,
        sample=sample,
        message="Sample uploaded successfully",
    )


@router.post("/hotwords/{hotword_id}/samples/browser-recording", response_model=SampleUploadResponse)
async def upload_browser_recording(hotword_id: str, file: UploadFile = File(...)) -> SampleUploadResponse:
    hotword = get_hotword(hotword_id)
    if not hotword:
        return build_error_response("hotword not found", "hotword_not_found", status.HTTP_404_NOT_FOUND)

    sample = await save_upload_file(hotword_id, file, prefix="recording")
    return SampleUploadResponse(
        service=settings.service_name,
        status="ok",
        hotword_id=hotword_id,
        sample=sample,
        message="Browser recording stored successfully",
    )


@router.post("/hotwords/{hotword_id}/model/upload", response_model=HotwordModelUploadResponse)
async def upload_hotword_model(hotword_id: str, file: UploadFile = File(...)) -> HotwordModelUploadResponse:
    hotword = get_hotword(hotword_id)
    if not hotword:
        return build_error_response("hotword not found", "hotword_not_found", status.HTTP_404_NOT_FOUND)

    try:
        model_path = await save_model_file(hotword_id, file)
    except ValueError as exc:
        return build_error_response(str(exc), "model_upload_failed", status.HTTP_422_UNPROCESSABLE_ENTITY)

    updated_hotword = get_hotword(hotword_id)
    assert updated_hotword is not None
    return HotwordModelUploadResponse(
        service=settings.service_name,
        status="ok",
        hotword_id=hotword_id,
        model_path=model_path,
        engine_type=updated_hotword.engine_type,
        model_ready=updated_hotword.model_ready,
        message="Legacy Porcupine model uploaded successfully",
    )


@router.post("/hotwords/{hotword_id}/build-model", response_model=ModelBuildResponse)
def build_hotword_model(hotword_id: str) -> ModelBuildResponse:
    try:
        return build_model(hotword_id)
    except ValueError as exc:
        detail = str(exc)
        if detail == "hotword not found":
            return build_error_response(detail, "hotword_not_found", status.HTTP_404_NOT_FOUND)
        return build_error_response(detail, "model_build_failed", status.HTTP_422_UNPROCESSABLE_ENTITY)


@router.get("/hotwords/{hotword_id}/model-status", response_model=ModelStatusResponse)
def hotword_model_status(hotword_id: str) -> ModelStatusResponse:
    try:
        return get_model_status(hotword_id)
    except ValueError:
        return build_error_response("hotword not found", "hotword_not_found", status.HTTP_404_NOT_FOUND)


@router.post("/detect", response_model=DetectResponse)
def detect(request: DetectRequest) -> DetectResponse:
    try:
        return detect_hotword(request.file_path, request.hotword_id)
    except ValueError as exc:
        detail = str(exc)
        error = "audio_file_not_found" if detail.startswith("audio file not found") else "detect_failed"
        status_code = status.HTTP_404_NOT_FOUND if error == "audio_file_not_found" else status.HTTP_422_UNPROCESSABLE_ENTITY
        return build_error_response(detail, error, status_code)


@router.post("/detect/upload", response_model=DetectUploadResponse)
async def detect_upload(
    file: UploadFile = File(...),
    hotword_id: str | None = None,
) -> DetectUploadResponse:
    saved_file = await save_test_upload(file)
    try:
        result = detect_hotword(saved_file.path, hotword_id)
    except ValueError as exc:
        return build_error_response(str(exc), "detect_failed", status.HTTP_422_UNPROCESSABLE_ENTITY)

    return DetectUploadResponse(
        service=settings.service_name,
        status="ok",
        file=saved_file,
        result=result,
    )


@router.get("/runtime/status", response_model=RuntimeStatusResponse)
def runtime_status() -> RuntimeStatusResponse:
    return get_runtime_status()


@router.post("/runtime/start", response_model=RuntimeControlResponse)
def runtime_start() -> RuntimeControlResponse:
    return start_runtime_listener()


@router.post("/runtime/stop", response_model=RuntimeControlResponse)
def runtime_stop() -> RuntimeControlResponse:
    return stop_runtime_listener()


@router.post("/runtime/test-trigger", response_model=RuntimeTriggerResponse)
def runtime_test_trigger() -> RuntimeTriggerResponse:
    return test_runtime_trigger()


@router.get("/runtime/config", response_model=RuntimeConfigResponse)
def runtime_config() -> RuntimeConfigResponse:
    return get_runtime_config()


@router.post("/runtime/reload-hotwords", response_model=RuntimeControlResponse)
def runtime_reload_hotwords() -> RuntimeControlResponse:
    return reload_runtime_hotwords()


@router.post("/runtime/configure-listener", response_model=RuntimeControlResponse)
def runtime_configure_listener(
    request: RuntimeListenerConfigRequest,
) -> RuntimeControlResponse:
    return configure_runtime_listener(request.enabled)


@router.get("/runtime/audio-devices", response_model=RuntimeAudioDevicesResponse)
def runtime_audio_devices() -> RuntimeAudioDevicesResponse:
    return get_runtime_audio_devices()


@router.post("/runtime/audio-input", response_model=RuntimeControlResponse)
def runtime_audio_input(
    request: RuntimeAudioInputRequest,
) -> RuntimeControlResponse:
    return configure_runtime_audio_input(request.device_name)


@router.post("/runtime/audio-probe", response_model=RuntimeAudioProbeResponse)
def runtime_audio_probe_run(
    request: RuntimeAudioProbeRequest,
) -> RuntimeAudioProbeResponse:
    try:
        return runtime_audio_probe(request.seconds)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/runtime/audio-probe/{file_name}")
def runtime_audio_probe_file(file_name: str) -> FileResponse:
    if "/" in file_name or "\\" in file_name or ".." in file_name:
        raise HTTPException(status_code=400, detail="invalid_file_name")
    probe_path = settings.hotword_runtime_recordings_dir / "_probes" / file_name
    if not probe_path.exists():
        raise HTTPException(status_code=404, detail="probe_file_not_found")
    return FileResponse(path=str(probe_path), media_type="audio/wav", filename=file_name)


@router.get("/runtime/audio-tuning", response_model=RuntimeAudioTuningResponse)
def runtime_audio_tuning() -> RuntimeAudioTuningResponse:
    return get_runtime_audio_tuning()


@router.post("/runtime/audio-tuning", response_model=RuntimeAudioTuningResponse)
def runtime_audio_tuning_update(
    request: RuntimeAudioTuningRequest,
) -> RuntimeAudioTuningResponse:
    return configure_runtime_audio_tuning(
        input_gain=request.input_gain,
        min_score=request.min_score,
        min_rms_factor=request.min_rms_factor,
        required_hits=request.required_hits,
    )


@router.get("/trainer/bootstrap")
async def trainer_bootstrap() -> JSONResponse:
    trainer_token, token_error = await _resolve_trainer_token()
    if not trainer_token:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "ok": False,
                "degraded": True,
                "warning": (token_error or {}).get("detail", "Trainer token unavailable."),
                "clients": [],
                "users": [],
                "profiles": [],
            },
        )

    headers = {"X-Jarvis-Trainer-Token": trainer_token}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                _build_family_url(settings.family_panel_trainer_bootstrap_path),
                headers=headers,
            )
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "ok": False,
                "degraded": True,
                "warning": f"Family Panel bootstrap unreachable: {exc}",
                "clients": [],
                "users": [],
                "profiles": [],
            },
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {"ok": False, "error": "invalid_family_response"}

    if response.status_code >= 400:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "ok": False,
                "degraded": True,
                "warning": (
                    payload.get("detail")
                    if isinstance(payload, dict)
                    else f"Family Panel bootstrap failed with HTTP {response.status_code}"
                ),
                "clients": [],
                "users": [],
                "profiles": [],
            },
        )

    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


@router.post("/trainer/ingest")
async def trainer_ingest(
    file: UploadFile = File(...),
    hotword_id: str = Form(...),
    client_id: int = Form(...),
    user_id: int = Form(...),
    jarvis_profile_id: int | None = Form(None),
    source: str | None = Form("browser"),
    intent_key: str | None = Form(None),
    intent_name: str | None = Form(None),
    intent_category: str | None = Form(None),
    intent_description: str | None = Form(None),
    handler_service: str | None = Form(None),
    handler_action: str | None = Form(None),
    slot_key: str | None = Form(None),
    slot_name: str | None = Form(None),
    slot_data_type: str | None = Form(None),
    memory_fact_key: str | None = Form(None),
    memory_scope: str | None = Form(None),
    memory_scope_identifier: str | None = Form(None),
) -> JSONResponse:
    hotword_id = hotword_id.strip().lower()
    if not hotword_id:
        return JSONResponse(status_code=422, content={"ok": False, "error": "missing_hotword_id"})
    if client_id <= 0 or user_id <= 0:
        return JSONResponse(status_code=422, content={"ok": False, "error": "missing_client_or_user"})
    trainer_token, token_error = await _resolve_trainer_token()
    if not trainer_token:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=token_error or {
                "ok": False,
                "error": "trainer_token_missing",
                "detail": "Trainer token unavailable.",
            },
        )

    hotword = get_hotword(hotword_id)
    if not hotword:
        return JSONResponse(status_code=404, content={"ok": False, "error": "hotword_not_found"})

    sample = await save_upload_file(hotword_id, file, prefix="trainer")
    transcript = ""
    stt_payload: dict[str, object] = {"ok": False, "error": "stt_not_called"}

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            stt_response = await client.post(
                f"{settings.stt_service_url.rstrip('/')}/transcribe",
                json={"file_path": sample.path},
            )
        try:
            stt_payload = stt_response.json()
        except ValueError:
            stt_payload = {"ok": False, "error": "invalid_stt_response"}
        if stt_response.status_code == 200:
            transcript = str(stt_payload.get("transcript", "")).strip()
    except httpx.HTTPError as exc:
        stt_payload = {"ok": False, "error": "stt_unreachable", "detail": str(exc)}

    transcript = transcript or _value_or_demo(None, "DEMO TRANSCRIPT")
    normalized_hotword = hotword.phrase.strip() if hotword.phrase.strip() else hotword_id
    normalized_intent_key = _value_or_demo(
        intent_key,
        f"demo.{normalized_hotword.lower().replace(' ', '_')}",
    ).lower()
    normalized_intent_key = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in normalized_intent_key).strip("._-")
    if not normalized_intent_key:
        normalized_intent_key = "demo.fallback"

    trainer_payload = {
        "client_id": client_id,
        "user_id": user_id,
        "jarvis_profile_id": jarvis_profile_id or 0,
        "hotword_name": _value_or_demo(hotword.phrase, hotword_id),
        "source": _value_or_demo(source, "browser"),
        "transcript": transcript,
        "intent": {
            "intent_key": normalized_intent_key,
            "name": _value_or_demo(intent_name, f"{normalized_hotword} Trainer Intent"),
            "description": _value_or_demo(intent_description, "DEMO Beschreibung"),
            "category": _value_or_demo(intent_category, "hotword_trainer"),
            "response_template": _value_or_demo(None, "DEMO_RESPONSE"),
            "phrase": transcript,
            "language": "de",
            "match_type": "contains",
            "weight": 100,
            "phrase_notes": "DEMO",
        },
        "action": {
            "handler_service": _value_or_demo(handler_service, "DEMO_HANDLER"),
            "handler_action": _value_or_demo(handler_action, "DEMO_ACTION"),
        },
        "slots": [
            {
                "slot_key": _value_or_demo(slot_key, "demo_slot"),
                "name": _value_or_demo(slot_name, "DEMO SLOT"),
                "data_type": _value_or_demo(slot_data_type, "string"),
                "is_required": False,
                "is_multiple": False,
                "default_value": "DEMO",
                "validation_rule": "DEMO",
                "help_text": "DEMO",
                "position": 1,
            }
        ],
        "memory_lv1": {
            "name": "DEMO Memory",
            "fact_key": _value_or_demo(memory_fact_key, f"demo.fact.{normalized_intent_key.replace('.', '_')}"),
            "scope": _value_or_demo(memory_scope, "user"),
            "scope_identifier": _value_or_demo(memory_scope_identifier, str(user_id)),
            "value_type": "string",
            "value_text": transcript,
            "source_type": "hotword_trainer",
            "confidence": 0.95,
            "priority": 100,
            "notes": "DEMO",
        },
    }

    ingest_headers = {"X-Jarvis-Trainer-Token": trainer_token}
    try:
        with open(sample.path, "rb") as file_handle:
            files = {
                "file": (
                    Path(sample.path).name,
                    file_handle,
                    file.content_type or "application/octet-stream",
                )
            }
            data = {"payload": json.dumps(trainer_payload, ensure_ascii=False)}
            async with httpx.AsyncClient(timeout=40.0) as client:
                family_response = await client.post(
                    _build_family_url(settings.family_panel_trainer_ingest_path),
                    headers=ingest_headers,
                    data=data,
                    files=files,
                )
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "ok": False,
                "error": "family_ingest_failed",
                "detail": str(exc),
                "sample": sample.model_dump(mode="json"),
                "stt": stt_payload,
                "payload": trainer_payload,
            },
        )

    try:
        family_payload = family_response.json()
    except ValueError:
        family_payload = {"ok": False, "error": "invalid_family_response"}

    return JSONResponse(
        status_code=family_response.status_code,
        content={
            "ok": family_response.status_code < 400,
            "sample": sample.model_dump(mode="json"),
            "stt": stt_payload,
            "trainer_payload": trainer_payload,
            "family": family_payload,
        },
    )


@router.post("/trainer/hotword-sample")
async def trainer_hotword_sample(
    file: UploadFile = File(...),
    hotword_id: str = Form(...),
    source: str | None = Form("browser"),
) -> JSONResponse:
    hotword_id = hotword_id.strip().lower()
    if not hotword_id:
        return JSONResponse(status_code=422, content={"ok": False, "error": "missing_hotword_id"})

    hotword = get_hotword(hotword_id)
    if not hotword:
        return JSONResponse(status_code=404, content={"ok": False, "error": "hotword_not_found"})

    sample = await save_upload_file(hotword_id, file, prefix="trainer-hotword")

    stt_payload: dict[str, object] = {"ok": False, "error": "stt_not_called"}
    transcript = ""
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            stt_response = await client.post(
                f"{settings.stt_service_url.rstrip('/')}/transcribe",
                json={"file_path": sample.path},
            )
        try:
            stt_payload = stt_response.json()
        except ValueError:
            stt_payload = {"ok": False, "error": "invalid_stt_response"}
        if stt_response.status_code == 200:
            transcript = str(stt_payload.get("transcript", "")).strip()
    except httpx.HTTPError as exc:
        stt_payload = {"ok": False, "error": "stt_unreachable", "detail": str(exc)}

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "mode": "hotword_trainer",
            "source": _value_or_demo(source, "browser"),
            "hotword_id": hotword_id,
            "sample": sample.model_dump(mode="json"),
            "stt": stt_payload,
            "transcript": transcript or None,
        },
    )


@router.post("/assistant/hotwords/{hotword_id}/finalize")
async def assistant_finalize_hotword(hotword_id: str) -> JSONResponse:
    hotword_id = hotword_id.strip().lower()
    hotword = get_hotword(hotword_id)
    if not hotword:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": "hotword_not_found", "detail": "hotword not found"},
        )

    training_backend = (hotword.training_backend or "openwakeword-local").strip() or "openwakeword-local"
    trainer_base = settings.hotword_trainer_url.rstrip("/")
    steps: list[dict[str, object]] = []

    async def _trainer_post(path: str, payload: dict[str, object], step_name: str) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{trainer_base}{path}", json=payload)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"{step_name} failed: trainer unreachable ({exc})") from exc

        try:
            body = response.json()
        except ValueError:
            body = {"detail": "invalid trainer response"}

        if response.status_code >= 400:
            detail = body.get("detail") if isinstance(body, dict) else None
            raise RuntimeError(f"{step_name} failed: {detail or f'HTTP_{response.status_code}'}")

        if not isinstance(body, dict):
            raise RuntimeError(f"{step_name} failed: invalid trainer payload")

        steps.append({"step": step_name, "ok": True, "payload": body})
        return body

    try:
        dataset_payload = await _trainer_post(
            "/datasets/build",
            {"hotword_id": hotword_id, "training_backend": training_backend},
            "dataset_build",
        )
        train_payload = await _trainer_post(
            "/train",
            {"hotword_id": hotword_id, "training_backend": training_backend},
            "train",
        )
        if str(train_payload.get("job_status", "")).lower() != "completed":
            raise RuntimeError("train failed: training job did not complete successfully")
        export_payload = await _trainer_post(
            "/models/export",
            {"hotword_id": hotword_id},
            "export",
        )

        exported_model_path = str(export_payload.get("exported_model_path", "")).strip()
        if not exported_model_path:
            raise RuntimeError("export failed: no exported model path returned")

        updated_hotword = update_hotword(
            hotword_id,
            HotwordUpdateRequest(
                model_path=exported_model_path,
                model_format=str(export_payload.get("model_format", "")).strip() or "json",
                engine_type="local",
                training_backend=training_backend,
                runtime_enabled=True,
                is_active=True,
            ),
        )
        build_payload = build_model(hotword_id).model_dump(mode="json")
        steps.append({"step": "build_model", "ok": True, "payload": build_payload})

        runtime_status = get_runtime_status()
        if runtime_status.listener_running:
            runtime_payload = reload_runtime_hotwords().model_dump(mode="json")
            runtime_step = "runtime_reload"
        else:
            runtime_payload = start_runtime_listener().model_dump(mode="json")
            runtime_step = "runtime_start"
        steps.append({"step": runtime_step, "ok": True, "payload": runtime_payload})
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "ok": False,
                "error": "assistant_finalize_failed",
                "detail": str(exc),
                "hotword_id": hotword_id,
                "steps": steps,
            },
        )
    except RuntimeError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "ok": False,
                "error": "assistant_finalize_failed",
                "detail": str(exc),
                "hotword_id": hotword_id,
                "steps": steps,
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "hotword_id": hotword_id,
            "message": "Hotword wurde trainiert, exportiert und fuer die Runtime aktiviert.",
            "dataset": dataset_payload,
            "train": train_payload,
            "export": export_payload,
            "hotword": updated_hotword.model_dump(mode="json"),
            "steps": steps,
        },
    )
