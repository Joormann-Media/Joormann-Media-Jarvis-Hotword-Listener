from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


SERVICE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(SERVICE_DIR / ".env")


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "hotword-service")
    service_version: str = os.getenv("SERVICE_VERSION", "0.1.0")
    service_host: str = os.getenv("SERVICE_HOST", "127.0.0.1")
    service_port: int = int(os.getenv("SERVICE_PORT", "8116"))
    jarvis_env: str = os.getenv("JARVIS_ENV", "dev")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    hotword_data_dir: Path = Path(
        os.getenv("HOTWORD_DATA_DIR", str(PROJECT_ROOT / "runtime" / "hotwords"))
    )
    hotword_engine: str = os.getenv("HOTWORD_ENGINE", "local")
    hotword_listener_enabled: bool = parse_bool(
        os.getenv("HOTWORD_LISTENER_ENABLED"),
        False,
    )
    hotword_runtime_recordings_dir: Path = Path(
        os.getenv(
            "HOTWORD_RUNTIME_RECORDINGS_DIR",
            str(PROJECT_ROOT / "runtime" / "recordings" / "live"),
        )
    )
    hotword_runtime_cooldown_seconds: float = float(
        os.getenv("HOTWORD_RUNTIME_COOLDOWN_SECONDS", "6")
    )
    hotword_runtime_record_seconds: int = int(
        os.getenv("HOTWORD_RUNTIME_RECORD_SECONDS", "5")
    )
    hotword_runtime_retry_on_empty_transcript: bool = parse_bool(
        os.getenv("HOTWORD_RUNTIME_RETRY_ON_EMPTY_TRANSCRIPT"),
        True,
    )
    hotword_runtime_retry_extra_seconds: int = int(
        os.getenv("HOTWORD_RUNTIME_RETRY_EXTRA_SECONDS", "3")
    )
    hotword_runtime_device_index: int = int(
        os.getenv("HOTWORD_RUNTIME_DEVICE_INDEX", "-1")
    )
    hotword_runtime_device_name: str = os.getenv(
        "HOTWORD_RUNTIME_DEVICE_NAME",
        "",
    ).strip()
    hotword_runtime_followup_sample_rate: int = int(
        os.getenv("HOTWORD_RUNTIME_FOLLOWUP_SAMPLE_RATE", "16000")
    )
    hotword_runtime_required_hits: int = int(
        os.getenv("HOTWORD_RUNTIME_REQUIRED_HITS", "2")
    )
    hotword_runtime_min_score: float = float(
        os.getenv("HOTWORD_RUNTIME_MIN_SCORE", "0.62")
    )
    hotword_runtime_min_rms_factor: float = float(
        os.getenv("HOTWORD_RUNTIME_MIN_RMS_FACTOR", "0.35")
    )
    hotword_runtime_input_gain: float = float(
        os.getenv("HOTWORD_RUNTIME_INPUT_GAIN", "1.0")
    )
    hotword_followup_use_arecord: bool = parse_bool(
        os.getenv("HOTWORD_FOLLOWUP_USE_ARECORD"),
        True,
    )
    hotword_access_key: str = os.getenv("HOTWORD_ACCESS_KEY", "").strip()
    hotword_default_sensitivity: float = float(
        os.getenv("HOTWORD_DEFAULT_SENSITIVITY", "0.5")
    )
    hotword_runtime_dispatch_url: str = os.getenv(
        "HOTWORD_RUNTIME_DISPATCH_URL",
        "http://127.0.0.1:8110/voice/command",
    )
    hotword_trainer_url: str = os.getenv(
        "HOTWORD_TRAINER_URL",
        "http://127.0.0.1:8117",
    )
    speaker_id_service_url: str = os.getenv(
        "SPEAKER_ID_SERVICE_URL",
        "http://127.0.0.1:8113",
    )
    stt_service_url: str = os.getenv(
        "STT_SERVICE_URL",
        "http://127.0.0.1:8111",
    )
    family_panel_url: str = os.getenv(
        "FAMILY_PANEL_URL",
        "http://127.0.0.1:5093",
    )
    family_panel_trainer_bootstrap_path: str = os.getenv(
        "FAMILY_PANEL_TRAINER_BOOTSTRAP_PATH",
        "/api/jarvis/trainer/bootstrap",
    )
    family_panel_trainer_auto_token_path: str = os.getenv(
        "FAMILY_PANEL_TRAINER_AUTO_TOKEN_PATH",
        "/api/jarvis/trainer/auto-token",
    )
    family_panel_trainer_ingest_path: str = os.getenv(
        "FAMILY_PANEL_TRAINER_INGEST_PATH",
        "/api/jarvis/trainer/ingest",
    )
    family_panel_trainer_token: str = os.getenv(
        "FAMILY_PANEL_TRAINER_TOKEN",
        "",
    ).strip()
    family_panel_sync_token: str = os.getenv(
        "FAMILY_PANEL_SYNC_TOKEN",
        os.getenv("PORTAL_REGISTRY_PUSH_TOKEN", os.getenv("DEVICEPORTAL_SYNC_TOKEN", "")),
    ).strip()
    hotword_runtime_autoplay_response: bool = parse_bool(
        os.getenv("HOTWORD_RUNTIME_AUTOPLAY_RESPONSE"),
        False,
    )
    hotword_runtime_ignore_while_speaking: bool = parse_bool(
        os.getenv("HOTWORD_RUNTIME_IGNORE_WHILE_SPEAKING"),
        True,
    )
    hotword_runtime_speaking_guard_seconds: float = float(
        os.getenv("HOTWORD_RUNTIME_SPEAKING_GUARD_SECONDS", "3")
    )
    runtime_log_file: Path = Path(
        os.getenv(
            "HOTWORD_RUNTIME_LOG_FILE",
            str(PROJECT_ROOT / "runtime" / "logs" / "hotword-service.log"),
        )
    )
    hotword_runtime_log_to_stdout: bool = parse_bool(
        os.getenv("HOTWORD_RUNTIME_LOG_TO_STDOUT"),
        True,
    )
    runtime_state_file: Path = Path(
        os.getenv(
            "HOTWORD_RUNTIME_STATE_FILE",
            str(PROJECT_ROOT / "runtime" / "hotword-service-runtime.json"),
        )
    )
    speaker_data_dir: Path = Path(
        os.getenv("SPEAKER_DATA_DIR", str(PROJECT_ROOT / "runtime" / "voiceprints"))
    )


settings = Settings()
