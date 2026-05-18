from datetime import datetime
from typing import Any
import re

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    service: str
    status: str
    timestamp: datetime
    environment: str


class ErrorResponse(BaseModel):
    service: str
    status: str = "error"
    error: str
    detail: str
    timestamp: datetime


class SpeakerOptionResponse(BaseModel):
    id: str
    label: str
    is_active: bool
    hotwords: list[str] = Field(default_factory=list)


class HotwordCreateRequest(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    phrase: str = Field(min_length=1)
    speaker_ids: list[str] = Field(default_factory=list)
    notes: str | None = None
    sensitivity: float | None = None
    detection_mode: str | None = None
    engine_type: str | None = None
    model_path: str | None = None
    runtime_enabled: bool = False
    threshold_override: float | None = None
    training_backend: str | None = None
    model_format: str | None = None
    priority: int = Field(default=100, ge=0, le=100000)
    is_default: bool = False
    phrases: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = "-".join(value.strip().lower().split())
        if not normalized:
            raise ValueError("id must not be empty")
        return normalized

    @field_validator("label", "phrase")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("notes", "model_path", "engine_type", "training_backend", "model_format")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("speaker_ids", mode="before")
    @classmethod
    def normalize_speaker_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = value.split(",")
        else:
            items = list(value)
        return sorted({item.strip().lower() for item in items if str(item).strip()})

    @field_validator("phrases", mode="before")
    @classmethod
    def normalize_phrases(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = re.split(r"[,\s]+", value.strip())
        else:
            items = list(value)
        normalized = [str(item).strip() for item in items if str(item).strip()]
        return list(dict.fromkeys(normalized))


class HotwordUpdateRequest(BaseModel):
    label: str | None = None
    phrase: str | None = None
    speaker_ids: list[str] | None = None
    notes: str | None = None
    is_active: bool | None = None
    sensitivity: float | None = None
    detection_mode: str | None = None
    engine_type: str | None = None
    model_path: str | None = None
    runtime_enabled: bool | None = None
    threshold_override: float | None = None
    training_backend: str | None = None
    model_format: str | None = None
    priority: int | None = Field(default=None, ge=0, le=100000)
    is_default: bool | None = None
    phrases: list[str] | None = None

    @field_validator("label", "phrase")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("notes", "model_path", "engine_type", "training_backend", "model_format")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("speaker_ids", mode="before")
    @classmethod
    def normalize_speaker_ids(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            items = value.split(",")
        else:
            items = list(value)
        return sorted({item.strip().lower() for item in items if str(item).strip()})

    @field_validator("phrases", mode="before")
    @classmethod
    def normalize_phrases(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            items = re.split(r"[,\s]+", value.strip())
        else:
            items = list(value)
        normalized = [str(item).strip() for item in items if str(item).strip()]
        return list(dict.fromkeys(normalized))


class HotwordResponse(BaseModel):
    id: str
    label: str
    phrase: str
    speaker_ids: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    notes: str | None = None
    sample_count: int
    model_ready: bool
    engine_type: str
    model_path: str | None = None
    runtime_enabled: bool = False
    threshold_override: float | None = None
    sensitivity: float | None = None
    detection_mode: str | None = None
    last_built_at: datetime | None = None
    last_trained_at: datetime | None = None
    training_backend: str | None = None
    model_format: str | None = None
    priority: int = 100
    is_default: bool = False
    phrases: list[str] = Field(default_factory=list)


class HotwordListResponse(BaseModel):
    service: str
    status: str
    hotwords: list[HotwordResponse]


class HotwordDetailResponse(BaseModel):
    service: str
    status: str
    hotword: HotwordResponse
    samples: list["SampleResponse"]


class HotwordCreateResponse(BaseModel):
    service: str
    status: str
    hotword: HotwordResponse
    message: str


class HotwordUpdateResponse(BaseModel):
    service: str
    status: str
    hotword: HotwordResponse
    message: str


class HotwordDeleteResponse(BaseModel):
    service: str
    status: str
    hotword_id: str
    message: str


class HotwordBulkDeleteResponse(BaseModel):
    service: str
    status: str
    deleted_hotword_ids: list[str] = Field(default_factory=list)
    message: str


class SampleResponse(BaseModel):
    filename: str
    path: str
    created_at: datetime
    size_bytes: int


class SampleListResponse(BaseModel):
    service: str
    status: str
    hotword_id: str
    samples: list[SampleResponse]


class SampleUploadResponse(BaseModel):
    service: str
    status: str
    hotword_id: str
    sample: SampleResponse
    message: str


class HotwordModelUploadResponse(BaseModel):
    service: str
    status: str
    hotword_id: str
    model_path: str
    engine_type: str
    model_ready: bool
    message: str


class ModelBuildResponse(BaseModel):
    service: str
    status: str
    hotword_id: str
    sample_count: int
    model_ready: bool
    engine_type: str
    message: str


class ModelStatusResponse(BaseModel):
    service: str
    status: str
    hotword_id: str
    sample_count: int
    model_ready: bool
    engine_type: str
    last_built_at: datetime | None = None


class DetectRequest(BaseModel):
    file_path: str | None = None
    hotword_id: str | None = None

    @field_validator("file_path", "hotword_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DetectResponse(BaseModel):
    service: str
    status: str
    matched: bool
    hotword: dict[str, Any] | None
    speaker_ids: list[str]
    simulated: bool
    message: str


class DetectUploadResponse(BaseModel):
    service: str
    status: str
    file: SampleResponse
    result: DetectResponse


class RuntimeStatusResponse(BaseModel):
    service: str
    status: str
    engine: str
    listener_running: bool
    running: bool
    configured_enabled: bool
    cooldown_active: bool
    ignore_while_speaking: bool
    speaking_active: bool
    message: str
    device_index: int
    device_name: str | None = None
    followup_sample_rate: int
    default_sensitivity: float
    active_hotwords: list[str] = Field(default_factory=list)
    active_hotword_count: int = 0
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


class RuntimeControlResponse(BaseModel):
    service: str
    status: str
    engine: str
    listener_running: bool
    running: bool
    configured_enabled: bool
    cooldown_active: bool
    ignore_while_speaking: bool
    speaking_active: bool
    message: str
    device_index: int
    device_name: str | None = None
    followup_sample_rate: int
    default_sensitivity: float
    active_hotwords: list[str] = Field(default_factory=list)
    active_hotword_count: int = 0
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


class RuntimeTriggerResponse(RuntimeControlResponse):
    trigger_accepted: bool


class RuntimeListenerConfigRequest(BaseModel):
    enabled: bool


class RuntimeAudioTuningRequest(BaseModel):
    input_gain: float | None = None
    min_score: float | None = None
    min_rms_factor: float | None = None
    required_hits: int | None = None


class RuntimeAudioTuningResponse(BaseModel):
    service: str
    status: str
    input_gain: float
    min_score: float
    min_rms_factor: float
    required_hits: int
    message: str


class RuntimeAudioInputRequest(BaseModel):
    device_name: str | None = None


class AudioDeviceOptionResponse(BaseModel):
    value: str
    label: str


class RuntimeAudioDevicesResponse(BaseModel):
    service: str
    status: str
    configured_device_name: str | None = None
    devices: list[AudioDeviceOptionResponse] = Field(default_factory=list)


class RuntimeAudioProbeRequest(BaseModel):
    seconds: int = Field(default=3, ge=1, le=10)


class RuntimeAudioProbeResponse(BaseModel):
    service: str
    status: str
    seconds: int
    sample_rate: int
    sample_count: int
    rms: float
    peak: float
    detected_signal: bool
    device_name: str | None = None
    file_name: str
    file_path: str
    playback_url: str
    message: str


class RuntimeConfigResponse(BaseModel):
    service: str
    status: str
    engine: str
    listener_enabled: bool
    device_index: int
    device_name: str | None = None
    access_key_configured: bool
    cooldown_seconds: float
    record_seconds: int
    followup_sample_rate: int
    followup_use_arecord: bool
    dispatch_url: str
    ignore_while_speaking: bool
    default_sensitivity: float
    active_hotwords: list[dict[str, Any]] = Field(default_factory=list)


class SpeakerListReferenceResponse(BaseModel):
    service: str
    status: str
    speakers: list[SpeakerOptionResponse]
