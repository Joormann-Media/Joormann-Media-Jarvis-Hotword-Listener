import json
from dataclasses import dataclass
from pathlib import Path

from .local_features import cosine_similarity, rms, sample_feature_vector


@dataclass(frozen=True)
class LocalModelArtifact:
    hotword_id: str
    label: str
    phrase: str
    sample_rate: int
    channels: int
    feature_bins: int
    sample_count: int
    avg_duration_sec: float
    avg_rms: float
    prototype_envelope: list[float]
    actual_model_format: str

    @property
    def window_samples(self) -> int:
        return max(1, int(self.avg_duration_sec * self.sample_rate))


def load_local_model(path: Path) -> LocalModelArtifact:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"local model not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"local model is not valid JSON: {path}") from exc

    required_fields = (
        "hotword_id",
        "label",
        "phrase",
        "sample_rate",
        "channels",
        "feature_bins",
        "sample_count",
        "avg_duration_sec",
        "avg_rms",
        "prototype_envelope",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"local model is missing required fields: {', '.join(missing)}")

    prototype = payload["prototype_envelope"]
    if not isinstance(prototype, list) or not prototype:
        raise ValueError("local model prototype_envelope must be a non-empty list")

    return LocalModelArtifact(
        hotword_id=str(payload["hotword_id"]),
        label=str(payload["label"]),
        phrase=str(payload["phrase"]),
        sample_rate=int(payload["sample_rate"]),
        channels=int(payload["channels"]),
        feature_bins=int(payload["feature_bins"]),
        sample_count=int(payload["sample_count"]),
        avg_duration_sec=float(payload["avg_duration_sec"]),
        avg_rms=float(payload["avg_rms"]),
        prototype_envelope=[float(value) for value in prototype],
        actual_model_format=str(payload.get("actual_model_format", "json")),
    )


def score_window(samples: list[float], model: LocalModelArtifact) -> float:
    features = sample_feature_vector(samples, bins=model.feature_bins)
    envelope_score = (cosine_similarity(features, model.prototype_envelope) + 1.0) / 2.0
    rms_value = rms(samples)
    rms_baseline = max(model.avg_rms, 1e-6)
    rms_delta = abs(rms_value - model.avg_rms) / rms_baseline
    energy_score = max(0.0, 1.0 - min(1.0, rms_delta))
    return (0.75 * envelope_score) + (0.25 * energy_score)


def score_samples(samples: list[float], sample_rate: int, model: LocalModelArtifact) -> float:
    if sample_rate != model.sample_rate:
        raise ValueError(f"expected {model.sample_rate} Hz audio, got {sample_rate} Hz")
    if not samples:
        return 0.0

    window_samples = min(model.window_samples, len(samples))
    if len(samples) <= window_samples:
        return score_window(samples, model)

    step = max(1, window_samples // 4)
    best_score = 0.0
    for start in range(0, len(samples) - window_samples + 1, step):
        window = samples[start:start + window_samples]
        best_score = max(best_score, score_window(window, model))
    return best_score
