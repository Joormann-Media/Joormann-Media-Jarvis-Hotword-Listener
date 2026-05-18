import json
import shutil
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from .config import settings
from .schemas import (
    HotwordCreateRequest,
    HotwordResponse,
    HotwordUpdateRequest,
    SampleResponse,
    SpeakerOptionResponse,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_priority(value: Any, fallback: int = 100) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = fallback
    return max(0, normalized)


def normalize_phrases(value: Any, fallback_phrase: str) -> list[str]:
    if value is None:
        return [fallback_phrase]
    if isinstance(value, str):
        raw_items = value.replace(",", " ").split()
    else:
        raw_items = [str(item).strip() for item in list(value)]
    cleaned = [item.strip() for item in raw_items if str(item).strip()]
    if not cleaned:
        return [fallback_phrase]
    # stable dedupe
    return list(dict.fromkeys(cleaned))


def ensure_storage() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    hotwords_dir().mkdir(parents=True, exist_ok=True)
    test_uploads_dir().mkdir(parents=True, exist_ok=True)
    metadata_path().touch(exist_ok=True)
    if not metadata_path().read_text(encoding="utf-8").strip():
        metadata_path().write_text("[]\n", encoding="utf-8")


def data_dir() -> Path:
    return settings.hotword_data_dir


def hotwords_dir() -> Path:
    return data_dir() / "hotwords"


def metadata_path() -> Path:
    return data_dir() / "hotwords.json"


def test_uploads_dir() -> Path:
    return data_dir() / "test_uploads"


def hotword_dir(hotword_id: str) -> Path:
    return hotwords_dir() / hotword_id


def hotword_metadata_path(hotword_id: str) -> Path:
    return hotword_dir(hotword_id) / "metadata.json"


def hotword_samples_dir(hotword_id: str) -> Path:
    return hotword_dir(hotword_id) / "samples"


def hotword_models_dir(hotword_id: str) -> Path:
    return hotword_dir(hotword_id) / "models"


def hotword_model_path(hotword_id: str) -> Path:
    return hotword_models_dir(hotword_id) / "model.json"


def hotword_tests_dir(hotword_id: str) -> Path:
    return hotword_dir(hotword_id) / "tests"


def load_hotword_index() -> list[dict[str, Any]]:
    ensure_storage()
    try:
        entries = json.loads(metadata_path().read_text(encoding="utf-8"))
    except JSONDecodeError:
        entries = rebuild_index_from_hotword_dirs()
        save_hotword_index(entries)
    normalized_entries = [normalize_hotword_entry(entry) for entry in entries]
    if normalized_entries != entries:
        save_hotword_index(normalized_entries)
    return normalized_entries


def save_hotword_index(entries: list[dict[str, Any]]) -> None:
    normalized_entries = [normalize_hotword_entry(entry) for entry in entries]
    normalized_entries = normalize_default_hotword(normalized_entries)
    write_json_file(metadata_path(), sort_hotword_entries(normalized_entries))


def list_hotwords() -> list[HotwordResponse]:
    hotwords: list[HotwordResponse] = []
    for entry in sort_hotword_entries(load_hotword_index()):
        sample_count = len(list_samples(entry["id"]))
        hotwords.append(
            HotwordResponse(
                id=entry["id"],
                label=entry["label"],
                phrase=entry["phrase"],
                phrases=entry.get("phrases", [entry["phrase"]]),
                speaker_ids=entry.get("speaker_ids", []),
                is_active=entry.get("is_active", True),
                created_at=datetime.fromisoformat(entry["created_at"]),
                updated_at=datetime.fromisoformat(entry.get("updated_at", entry["created_at"])),
                notes=entry.get("notes"),
                sample_count=sample_count,
                model_ready=is_model_ready(entry),
                engine_type=entry.get("engine_type", settings.hotword_engine),
                model_path=entry.get("model_path"),
                runtime_enabled=bool(entry.get("runtime_enabled", False)),
                threshold_override=entry.get("threshold_override"),
                sensitivity=entry.get("sensitivity"),
                detection_mode=entry.get("detection_mode"),
                last_built_at=(
                    datetime.fromisoformat(entry["last_built_at"])
                    if entry.get("last_built_at")
                    else None
                ),
                last_trained_at=(
                    datetime.fromisoformat(entry["last_trained_at"])
                    if entry.get("last_trained_at")
                    else None
                ),
                training_backend=entry.get("training_backend"),
                model_format=entry.get("model_format"),
                priority=normalize_priority(entry.get("priority", 100)),
                is_default=bool(entry.get("is_default", False)),
            )
        )
    return hotwords


def get_hotword(hotword_id: str) -> HotwordResponse | None:
    for hotword in list_hotwords():
        if hotword.id == hotword_id:
            return hotword
    return None


def list_runtime_hotwords() -> list[HotwordResponse]:
    return [
        hotword
        for hotword in list_hotwords()
        if hotword.is_active and hotword.runtime_enabled and hotword.model_ready
    ]


def create_hotword(request: HotwordCreateRequest) -> HotwordResponse:
    ensure_storage()
    if get_hotword(request.id):
        raise ValueError(f"hotword already exists: {request.id}")

    entry = normalize_hotword_entry(
        {
            "id": request.id,
            "label": request.label,
            "phrase": request.phrase,
            "phrases": normalize_phrases(request.phrases, request.phrase),
            "speaker_ids": request.speaker_ids,
            "is_active": True,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
            "notes": request.notes,
            "sample_count": 0,
            "model_ready": bool(request.model_path and Path(request.model_path).exists()),
            "engine_type": request.engine_type or settings.hotword_engine,
            "model_path": request.model_path,
            "runtime_enabled": request.runtime_enabled,
            "threshold_override": request.threshold_override,
            "sensitivity": request.sensitivity,
            "detection_mode": request.detection_mode,
            "training_backend": request.training_backend or "openwakeword-local",
            "model_format": request.model_format or infer_model_format(request.model_path),
            "last_built_at": None,
            "last_trained_at": None,
            "priority": normalize_priority(request.priority),
            "is_default": bool(request.is_default),
        }
    )
    index = load_hotword_index()
    if not index:
        entry["is_default"] = True
    index.append(entry)
    save_hotword_index(index)

    hotword_root = hotword_dir(request.id)
    hotword_root.mkdir(parents=True, exist_ok=True)
    hotword_samples_dir(request.id).mkdir(parents=True, exist_ok=True)
    hotword_models_dir(request.id).mkdir(parents=True, exist_ok=True)
    hotword_tests_dir(request.id).mkdir(parents=True, exist_ok=True)
    write_json_file(hotword_metadata_path(request.id), entry)

    hotword = get_hotword(request.id)
    if hotword is None:
        raise ValueError("hotword could not be created")
    return hotword


def update_hotword(hotword_id: str, request: HotwordUpdateRequest) -> HotwordResponse:
    entry = load_hotword_entry(hotword_id)
    if request.label is not None:
        entry["label"] = request.label
    if request.phrase is not None:
        entry["phrase"] = request.phrase
        if request.phrases is None:
            entry["phrases"] = normalize_phrases(entry.get("phrases"), request.phrase)
            if entry["phrases"]:
                entry["phrases"][0] = request.phrase
    if request.speaker_ids is not None:
        entry["speaker_ids"] = request.speaker_ids
    if request.notes is not None:
        entry["notes"] = request.notes
    if request.is_active is not None:
        entry["is_active"] = request.is_active
    if request.sensitivity is not None or "sensitivity" in request.model_fields_set:
        entry["sensitivity"] = request.sensitivity
    if request.detection_mode is not None or "detection_mode" in request.model_fields_set:
        entry["detection_mode"] = request.detection_mode
    if request.engine_type is not None or "engine_type" in request.model_fields_set:
        entry["engine_type"] = request.engine_type or settings.hotword_engine
    if request.model_path is not None or "model_path" in request.model_fields_set:
        entry["model_path"] = request.model_path
        entry["model_ready"] = bool(request.model_path and Path(request.model_path).exists())
    if request.runtime_enabled is not None:
        entry["runtime_enabled"] = request.runtime_enabled
    if request.threshold_override is not None or "threshold_override" in request.model_fields_set:
        entry["threshold_override"] = request.threshold_override
    if request.training_backend is not None or "training_backend" in request.model_fields_set:
        entry["training_backend"] = request.training_backend
    if request.model_format is not None or "model_format" in request.model_fields_set:
        entry["model_format"] = request.model_format
    if request.phrases is not None or "phrases" in request.model_fields_set:
        phrase_fallback = request.phrase or entry.get("phrase") or hotword_id
        entry["phrases"] = normalize_phrases(request.phrases, phrase_fallback)
        entry["phrase"] = entry["phrases"][0]
    if request.priority is not None or "priority" in request.model_fields_set:
        entry["priority"] = normalize_priority(request.priority, fallback=0)
    if request.is_default is not None or "is_default" in request.model_fields_set:
        entry["is_default"] = bool(request.is_default)
    entry["updated_at"] = utc_now().isoformat()
    if entry.get("model_path") and not entry.get("model_format"):
        entry["model_format"] = infer_model_format(entry.get("model_path"))
    save_hotword_entry(hotword_id, entry)

    hotword = get_hotword(hotword_id)
    if hotword is None:
        raise ValueError("hotword not found")
    return hotword


def delete_hotword(hotword_id: str) -> bool:
    index = load_hotword_index()
    existing = [entry for entry in index if entry["id"] == hotword_id]
    if not existing:
        return False

    remaining = [entry for entry in index if entry["id"] != hotword_id]
    save_hotword_index(remaining)

    root_dir = hotword_dir(hotword_id)
    if root_dir.exists():
        shutil.rmtree(root_dir, ignore_errors=True)
    return True


def delete_all_hotwords() -> list[str]:
    existing_ids = [entry["id"] for entry in load_hotword_index()]
    save_hotword_index([])
    root = hotwords_dir()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return existing_ids


def list_samples(hotword_id: str) -> list[SampleResponse]:
    samples_root = hotword_samples_dir(hotword_id)
    if not samples_root.exists():
        return []

    samples: list[SampleResponse] = []
    for file_path in sorted(samples_root.iterdir()):
        if not file_path.is_file():
            continue
        stats = file_path.stat()
        samples.append(
            SampleResponse(
                filename=file_path.name,
                path=str(file_path),
                created_at=datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc),
                size_bytes=stats.st_size,
            )
        )
    return samples


async def save_upload_file(hotword_id: str, upload: UploadFile, prefix: str) -> SampleResponse:
    extension = Path(upload.filename or "sample.bin").suffix or ".bin"
    filename = f"{prefix}_{utc_now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid4().hex[:8]}{extension}"
    destination = hotword_samples_dir(hotword_id) / filename
    destination.parent.mkdir(parents=True, exist_ok=True)

    data = await upload.read()
    destination.write_bytes(data)
    touch_hotword_metadata(hotword_id, invalidate_model=True)
    stats = destination.stat()
    return SampleResponse(
        filename=destination.name,
        path=str(destination),
        created_at=datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc),
        size_bytes=stats.st_size,
    )


async def save_test_upload(upload: UploadFile) -> SampleResponse:
    extension = Path(upload.filename or "detect.bin").suffix or ".bin"
    filename = f"detect_{utc_now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid4().hex[:8]}{extension}"
    destination = test_uploads_dir() / filename
    data = await upload.read()
    destination.write_bytes(data)
    stats = destination.stat()
    return SampleResponse(
        filename=destination.name,
        path=str(destination),
        created_at=datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc),
        size_bytes=stats.st_size,
    )


def list_available_speakers() -> list[SpeakerOptionResponse]:
    speakers_dir = settings.speaker_data_dir / "speakers"
    if not speakers_dir.exists():
        return []

    speakers: list[SpeakerOptionResponse] = []
    for metadata_file in sorted(speakers_dir.glob("*/metadata.json")):
        try:
            payload = json.loads(metadata_file.read_text(encoding="utf-8"))
        except JSONDecodeError:
            continue
        speakers.append(
            SpeakerOptionResponse(
                id=payload["id"],
                label=payload.get("label", payload["id"].title()),
                is_active=payload.get("is_active", True),
                hotwords=sorted(
                    {
                        item.strip().lower()
                        for item in payload.get("hotwords", [])
                        if str(item).strip()
                    }
                ),
            )
        )
    return speakers


def load_hotword_entry(hotword_id: str) -> dict[str, Any]:
    for entry in load_hotword_index():
        if entry["id"] == hotword_id:
            return entry
    raise ValueError("hotword not found")


def save_hotword_entry(hotword_id: str, hotword_entry: dict[str, Any]) -> None:
    index = load_hotword_index()
    updated_entries = [
        hotword_entry if entry["id"] == hotword_id else entry
        for entry in index
    ]
    save_hotword_index(updated_entries)
    write_json_file(hotword_metadata_path(hotword_id), hotword_entry)


def touch_hotword_metadata(hotword_id: str, invalidate_model: bool = False) -> None:
    entry = load_hotword_entry(hotword_id)
    entry["updated_at"] = utc_now().isoformat()
    if invalidate_model:
        entry["model_ready"] = False
        entry["last_built_at"] = None
        model_file = hotword_model_path(hotword_id)
        if model_file.exists():
            model_file.unlink()
    save_hotword_entry(hotword_id, entry)


def normalize_hotword_entry(entry: dict[str, Any]) -> dict[str, Any]:
    created_at = entry.get("created_at") or utc_now().isoformat()
    return {
        "id": entry["id"],
        "label": entry.get("label", entry["id"].title()),
        "phrase": entry.get("phrase", entry["id"]),
        "phrases": normalize_phrases(entry.get("phrases"), entry.get("phrase", entry["id"])),
        "speaker_ids": sorted(
            {item.strip().lower() for item in entry.get("speaker_ids", []) if str(item).strip()}
        ),
        "is_active": entry.get("is_active", True),
        "created_at": created_at,
        "updated_at": entry.get("updated_at", created_at),
        "notes": entry.get("notes"),
        "model_ready": is_model_ready(entry),
        "engine_type": entry.get("engine_type", settings.hotword_engine),
        "model_path": entry.get("model_path"),
        "runtime_enabled": bool(entry.get("runtime_enabled", False)),
        "threshold_override": entry.get("threshold_override"),
        "sensitivity": entry.get("sensitivity"),
        "detection_mode": entry.get("detection_mode"),
        "last_built_at": entry.get("last_built_at"),
        "last_trained_at": entry.get("last_trained_at"),
        "training_backend": entry.get("training_backend", "openwakeword-local"),
        "model_format": entry.get("model_format") or infer_model_format(entry.get("model_path")),
        "priority": normalize_priority(entry.get("priority", 100)),
        "is_default": bool(entry.get("is_default", False)),
    }


def rebuild_index_from_hotword_dirs() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for metadata_file in hotwords_dir().glob("*/metadata.json"):
        try:
            payload = json.loads(metadata_file.read_text(encoding="utf-8"))
        except JSONDecodeError:
            continue
        entries.append(normalize_hotword_entry(payload))
    return sort_hotword_entries(normalize_default_hotword(entries))


def sort_hotword_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda item: (
            0 if bool(item.get("is_default", False)) else 1,
            normalize_priority(item.get("priority", 100)),
            str(item.get("label", item.get("id", ""))).lower(),
            item.get("id", ""),
        ),
    )


def normalize_default_hotword(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not entries:
        return entries

    sorted_entries = sort_hotword_entries(entries)
    has_default = any(bool(entry.get("is_default", False)) for entry in sorted_entries)
    if not has_default:
        sorted_entries[0]["is_default"] = True
        return sorted_entries

    first_default_found = False
    for entry in sorted_entries:
        if bool(entry.get("is_default", False)) and not first_default_found:
            first_default_found = True
            entry["is_default"] = True
        elif bool(entry.get("is_default", False)):
            entry["is_default"] = False
    return sorted_entries


def write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def is_model_ready(entry: dict[str, Any]) -> bool:
    model_path = entry.get("model_path")
    if not model_path:
        return False
    return Path(model_path).exists()


def infer_model_format(model_path: str | None) -> str | None:
    if not model_path:
        return None
    suffix = Path(model_path).suffix.lower().lstrip(".")
    return suffix or None


async def save_model_file(hotword_id: str, upload: UploadFile) -> str:
    extension = Path(upload.filename or "keyword.ppn").suffix.lower() or ".ppn"
    if extension != ".ppn":
        raise ValueError("Porcupine keyword models must use the .ppn extension")

    filename = f"{hotword_id}_{utc_now().strftime('%Y%m%d_%H%M%S_%f')}.ppn"
    destination = hotword_models_dir(hotword_id) / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = await upload.read()
    destination.write_bytes(data)

    entry = load_hotword_entry(hotword_id)
    entry["model_path"] = str(destination)
    entry["model_ready"] = True
    entry["engine_type"] = "porcupine"
    entry["training_backend"] = entry.get("training_backend") or "porcupine-legacy"
    entry["model_format"] = "ppn"
    entry["updated_at"] = utc_now().isoformat()
    save_hotword_entry(hotword_id, entry)
    return str(destination)
