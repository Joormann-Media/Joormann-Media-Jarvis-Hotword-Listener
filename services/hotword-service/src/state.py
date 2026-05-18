import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .config import settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def deserialize_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


@dataclass
class RuntimeSnapshot:
    listener_running: bool = False
    message: str = "Hotword listener is idle"
    active_hotwords: list[str] | None = None
    last_started_at: datetime | None = None
    last_stopped_at: datetime | None = None
    last_triggered_at: datetime | None = None
    last_detected_hotword: str | None = None
    last_detection_score: float | None = None
    last_recording_file: str | None = None
    last_dispatch_status: str | None = None
    last_dispatch_message: str | None = None
    last_input_transcript: str | None = None
    last_speaker_id: str | None = None
    last_response_audio_file: str | None = None
    speaking_active: bool = False
    speaking_until: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "last_started_at",
            "last_stopped_at",
            "last_triggered_at",
            "speaking_until",
        ):
            payload[key] = serialize_datetime(payload[key])
        return payload


class RuntimeStateStore:
    def __init__(self, state_file: Path, cooldown_seconds: float) -> None:
        self._state_file = state_file
        self._cooldown_seconds = cooldown_seconds
        self._lock = Lock()
        self._snapshot = RuntimeSnapshot()
        self._load()

    def _load(self) -> None:
        if not self._state_file.exists():
            return
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._snapshot = RuntimeSnapshot(
            listener_running=bool(payload.get("listener_running", False)),
            message=payload.get("message", "Hotword listener is idle"),
            active_hotwords=list(payload.get("active_hotwords") or []),
            last_started_at=deserialize_datetime(payload.get("last_started_at")),
            last_stopped_at=deserialize_datetime(payload.get("last_stopped_at")),
            last_triggered_at=deserialize_datetime(payload.get("last_triggered_at")),
            last_detected_hotword=payload.get("last_detected_hotword"),
            last_detection_score=payload.get("last_detection_score"),
            last_recording_file=payload.get("last_recording_file"),
            last_dispatch_status=payload.get("last_dispatch_status"),
            last_dispatch_message=payload.get("last_dispatch_message"),
            last_input_transcript=payload.get("last_input_transcript"),
            last_speaker_id=payload.get("last_speaker_id"),
            last_response_audio_file=payload.get("last_response_audio_file"),
            speaking_active=bool(payload.get("speaking_active", False)),
            speaking_until=deserialize_datetime(payload.get("speaking_until")),
        )

    def _persist(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps(self._snapshot.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )

    def _clone_snapshot(self) -> RuntimeSnapshot:
        snapshot = self._snapshot
        return RuntimeSnapshot(
            listener_running=snapshot.listener_running,
            message=snapshot.message,
            active_hotwords=list(snapshot.active_hotwords or []),
            last_started_at=snapshot.last_started_at,
            last_stopped_at=snapshot.last_stopped_at,
            last_triggered_at=snapshot.last_triggered_at,
            last_detected_hotword=snapshot.last_detected_hotword,
            last_detection_score=snapshot.last_detection_score,
            last_recording_file=snapshot.last_recording_file,
            last_dispatch_status=snapshot.last_dispatch_status,
            last_dispatch_message=snapshot.last_dispatch_message,
            last_input_transcript=snapshot.last_input_transcript,
            last_speaker_id=snapshot.last_speaker_id,
            last_response_audio_file=snapshot.last_response_audio_file,
            speaking_active=snapshot.speaking_active,
            speaking_until=snapshot.speaking_until,
        )

    def read(self) -> RuntimeSnapshot:
        with self._lock:
            return self._clone_snapshot()

    def update(self, **changes: Any) -> RuntimeSnapshot:
        with self._lock:
            for key, value in changes.items():
                setattr(self._snapshot, key, value)
            self._persist()
            return self._clone_snapshot()

    def is_cooldown_active(self, now: datetime | None = None) -> bool:
        snapshot = self.read()
        if not snapshot.last_triggered_at:
            return False
        current_time = now or utc_now()
        return current_time < snapshot.last_triggered_at + timedelta(
            seconds=self._cooldown_seconds
        )

    def seconds_until_ready(self, now: datetime | None = None) -> float:
        snapshot = self.read()
        if not snapshot.last_triggered_at:
            return 0.0
        current_time = now or utc_now()
        remaining = (
            snapshot.last_triggered_at
            + timedelta(seconds=self._cooldown_seconds)
            - current_time
        ).total_seconds()
        return max(0.0, remaining)

    def is_speaking_active(self, now: datetime | None = None) -> bool:
        snapshot = self.read()
        if not snapshot.speaking_until:
            return False
        current_time = now or utc_now()
        return current_time < snapshot.speaking_until


runtime_state = RuntimeStateStore(
    state_file=settings.runtime_state_file,
    cooldown_seconds=settings.hotword_runtime_cooldown_seconds,
)
