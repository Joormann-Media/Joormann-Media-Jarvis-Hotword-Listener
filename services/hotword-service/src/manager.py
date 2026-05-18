from pathlib import Path

from .config import settings
from .engine_adapter import get_engine_adapter
from .schemas import DetectResponse, ModelBuildResponse, ModelStatusResponse
from .storage import (
    get_hotword,
    hotword_model_path,
    list_hotwords,
    list_samples,
    load_hotword_entry,
    save_hotword_entry,
    utc_now,
    write_json_file,
)


def build_model(hotword_id: str) -> ModelBuildResponse:
    hotword = get_hotword(hotword_id)
    if hotword is None:
        raise ValueError("hotword not found")

    samples = list_samples(hotword_id)
    if not samples:
        raise ValueError("at least one sample is required")

    adapter = get_engine_adapter(settings.hotword_engine)
    metadata = adapter.build_model(hotword, [Path(sample.path) for sample in samples])
    entry = load_hotword_entry(hotword_id)
    entry["model_ready"] = bool(metadata.get("model_ready", hotword.model_ready))
    entry["last_built_at"] = utc_now().isoformat()
    entry["engine_type"] = str(metadata["engine_type"])
    entry["updated_at"] = utc_now().isoformat()
    if entry["model_ready"]:
        entry["last_trained_at"] = entry["last_built_at"]
    save_hotword_entry(hotword_id, entry)

    write_json_file(
        hotword_model_path(hotword_id),
        {
            "hotword_id": hotword_id,
            "engine_type": metadata["engine_type"],
            "built_at": entry["last_built_at"],
            "sample_count": len(samples),
            "message": metadata["message"],
            "model_ready": entry["model_ready"],
        },
    )

    return ModelBuildResponse(
        service=settings.service_name,
        status="ok",
        hotword_id=hotword_id,
        sample_count=len(samples),
        model_ready=entry["model_ready"],
        engine_type=str(metadata["engine_type"]),
        message=str(metadata["message"]),
    )


def get_model_status(hotword_id: str) -> ModelStatusResponse:
    hotword = get_hotword(hotword_id)
    if hotword is None:
        raise ValueError("hotword not found")

    return ModelStatusResponse(
        service=settings.service_name,
        status="ok",
        hotword_id=hotword_id,
        sample_count=hotword.sample_count,
        model_ready=hotword.model_ready,
        engine_type=hotword.engine_type,
        last_built_at=hotword.last_built_at,
    )


def detect_hotword(file_path: str | None, hotword_id: str | None = None) -> DetectResponse:
    if not file_path:
        return DetectResponse(
            service=settings.service_name,
            status="ok",
            matched=False,
            hotword=None,
            speaker_ids=[],
            simulated=settings.hotword_engine == "placeholder",
            message="No audio file provided for detection",
        )

    audio_path = Path(file_path)
    if not audio_path.exists():
        raise ValueError(f"audio file not found: {audio_path}")

    candidates = [
        hotword
        for hotword in list_hotwords()
        if hotword.is_active and (hotword_id is None or hotword.id == hotword_id)
    ]
    if hotword_id and not candidates:
        raise ValueError("hotword not found")

    adapter = get_engine_adapter(settings.hotword_engine)
    try:
        matched_hotword, message = adapter.detect(audio_path, candidates)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc
    if matched_hotword is None:
        return DetectResponse(
            service=settings.service_name,
            status="ok",
            matched=False,
            hotword=None,
            speaker_ids=[],
            simulated=settings.hotword_engine == "placeholder",
            message=message,
        )

    return DetectResponse(
        service=settings.service_name,
        status="ok",
        matched=True,
        hotword={
            "id": matched_hotword.id,
            "label": matched_hotword.label,
            "phrase": matched_hotword.phrase,
            "engine_type": matched_hotword.engine_type,
        },
        speaker_ids=matched_hotword.speaker_ids,
        simulated=settings.hotword_engine == "placeholder",
        message=message,
    )
