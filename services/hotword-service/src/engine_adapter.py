import os
import struct
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol

from .config import settings
from .local_audio import LocalAudioStream, LocalAudioStreamError
from .local_features import pcm16_bytes_to_floats, read_wav_floats, rms
from .local_model import LocalModelArtifact, load_local_model, score_samples
from .schemas import HotwordResponse


def normalize_probe(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


@dataclass(frozen=True)
class TriggerEvent:
    source: str
    message: str
    hotword_id: str | None = None
    hotword_label: str | None = None
    score: float | None = None


@dataclass(frozen=True)
class RuntimeHotword:
    id: str
    label: str
    phrase: str
    engine_type: str
    model_path: str
    sensitivity: float


@dataclass(frozen=True)
class LoadedLocalHotword:
    runtime_hotword: RuntimeHotword
    model: LocalModelArtifact

    @property
    def id(self) -> str:
        return self.runtime_hotword.id

    @property
    def label(self) -> str:
        return self.runtime_hotword.label

    @property
    def threshold(self) -> float:
        return self.runtime_hotword.sensitivity


class HotwordEngineAdapter(Protocol):
    engine_type: str

    def build_model(self, hotword: HotwordResponse, sample_paths: list[Path]) -> dict[str, object]:
        ...

    def detect(self, file_path: Path, hotwords: list[HotwordResponse]) -> tuple[HotwordResponse | None, str]:
        ...

    def wait_for_trigger(self, stop_event: Event, poll_interval: float = 0.5) -> TriggerEvent | None:
        ...

    def request_manual_trigger(self) -> bool:
        ...

    def reload_hotwords(self, hotwords: list[HotwordResponse]) -> list[str]:
        ...

    def active_hotwords(self) -> list[str]:
        ...

    def active_hotword_count(self) -> int:
        ...


class PlaceholderEngineAdapter:
    engine_type = "placeholder"

    def __init__(self) -> None:
        self._manual_trigger = Event()
        self._active_hotwords: list[RuntimeHotword] = []

    def build_model(self, hotword: HotwordResponse, sample_paths: list[Path]) -> dict[str, object]:
        return {
            "engine_type": self.engine_type,
            "message": f"Placeholder model prepared from {len(sample_paths)} samples",
            "model_ready": False,
        }

    def detect(self, file_path: Path, hotwords: list[HotwordResponse]) -> tuple[HotwordResponse | None, str]:
        probe = normalize_probe(file_path.stem)
        for hotword in hotwords:
            hotword_tokens = {
                normalize_probe(hotword.id),
                normalize_probe(hotword.phrase),
                normalize_probe(hotword.label),
            }
            if any(token and token in probe for token in hotword_tokens):
                return hotword, "Placeholder filename-based hotword match"
        return None, "Hotword detection pipeline placeholder"

    def wait_for_trigger(self, stop_event: Event, poll_interval: float = 0.5) -> TriggerEvent | None:
        while not stop_event.is_set():
            if self._manual_trigger.wait(timeout=poll_interval):
                self._manual_trigger.clear()
                return TriggerEvent(source="manual", message="Placeholder manual trigger received")
        return None

    def request_manual_trigger(self) -> bool:
        self._manual_trigger.set()
        return True

    def reload_hotwords(self, hotwords: list[HotwordResponse]) -> list[str]:
        self._active_hotwords = [
            RuntimeHotword(
                id=hotword.id,
                label=hotword.label,
                phrase=hotword.phrase,
                engine_type=hotword.engine_type,
                model_path=hotword.model_path or "",
                sensitivity=_resolve_threshold(hotword),
            )
            for hotword in hotwords
        ]
        return self.active_hotwords()

    def active_hotwords(self) -> list[str]:
        return [hotword.id for hotword in self._active_hotwords]

    def active_hotword_count(self) -> int:
        return len(self._active_hotwords)


class OpenWakeWordLegacyAdapter(PlaceholderEngineAdapter):
    engine_type = "openwakeword"

    def build_model(self, hotword: HotwordResponse, sample_paths: list[Path]) -> dict[str, object]:
        return {
            "engine_type": self.engine_type,
            "message": "OpenWakeWord legacy runtime is not enabled in this phase",
            "model_ready": bool(hotword.model_path),
        }

    def detect(self, file_path: Path, hotwords: list[HotwordResponse]) -> tuple[HotwordResponse | None, str]:
        return None, "OpenWakeWord legacy runtime is not enabled in this phase"


class LocalEngineAdapter:
    engine_type = "local"

    def __init__(self) -> None:
        self._manual_trigger = Event()
        self._loaded_hotwords: list[LoadedLocalHotword] = []
        self._audio_stream: LocalAudioStream | None = None

    def build_model(self, hotword: HotwordResponse, sample_paths: list[Path]) -> dict[str, object]:
        model_ready = bool(hotword.model_path and Path(hotword.model_path).exists())
        if model_ready:
            return {
                "engine_type": self.engine_type,
                "message": "Local JSON model is available for runtime",
                "model_ready": True,
            }
        return {
            "engine_type": self.engine_type,
            "message": "Local training must export a JSON model before runtime can use this hotword",
            "model_ready": False,
        }

    def detect(self, file_path: Path, hotwords: list[HotwordResponse]) -> tuple[HotwordResponse | None, str]:
        loaded_hotwords = self._load_runtime_hotwords(hotwords)
        if not loaded_hotwords:
            return None, "No active local hotwords configured"

        samples, sample_rate = read_wav_floats(file_path)
        best_hotword: LoadedLocalHotword | None = None
        best_score = 0.0
        for loaded_hotword in loaded_hotwords:
            score = score_samples(samples, sample_rate, loaded_hotword.model)
            if score > best_score:
                best_score = score
                best_hotword = loaded_hotword

        if best_hotword is None:
            return None, "No local hotword match detected"
        if best_score < best_hotword.threshold:
            return None, f"Local hotword score {best_score:.3f} below threshold {best_hotword.threshold:.3f}"

        matched_hotword = next((hotword for hotword in hotwords if hotword.id == best_hotword.id), None)
        if matched_hotword is None:
            return None, "Matched local hotword is not available"
        return matched_hotword, f"Local model matched '{matched_hotword.id}' with score {best_score:.3f}"

    def wait_for_trigger(self, stop_event: Event, poll_interval: float = 0.5) -> TriggerEvent | None:
        if self._manual_trigger.is_set():
            self._manual_trigger.clear()
            return TriggerEvent(source="manual", message="Manual runtime trigger received")

        if not self._loaded_hotwords:
            stop_event.wait(timeout=poll_interval)
            return None

        max_window_samples = max(item.model.window_samples for item in self._loaded_hotwords)
        max_sample_rate = max(item.model.sample_rate for item in self._loaded_hotwords)
        chunk_samples = max(1024, max_sample_rate // 4)
        sample_buffer: deque[float] = deque(maxlen=max_window_samples)
        consecutive_hits: dict[str, int] = {}

        self._ensure_audio_stream(max_sample_rate)
        assert self._audio_stream is not None

        try:
            self._audio_stream.start()
            while not stop_event.is_set():
                if self._manual_trigger.is_set():
                    self._manual_trigger.clear()
                    return TriggerEvent(source="manual", message="Manual runtime trigger received")

                raw_audio = self._audio_stream.read(chunk_samples * 2)
                samples = pcm16_bytes_to_floats(raw_audio)
                tuning = self._runtime_tuning()
                gain = tuning["input_gain"]
                if gain != 1.0:
                    samples = [max(-1.0, min(1.0, sample * gain)) for sample in samples]
                sample_buffer.extend(samples)
                if len(sample_buffer) < min(item.model.window_samples for item in self._loaded_hotwords):
                    continue

                best_hotword: LoadedLocalHotword | None = None
                best_score = 0.0
                best_window: list[float] | None = None
                buffer_list = list(sample_buffer)
                for loaded_hotword in self._loaded_hotwords:
                    window = buffer_list[-loaded_hotword.model.window_samples:]
                    score = score_samples(window, loaded_hotword.model.sample_rate, loaded_hotword.model)
                    if score > best_score:
                        best_score = score
                        best_hotword = loaded_hotword
                        best_window = window

                if best_hotword:
                    effective_threshold = max(best_hotword.threshold, tuning["min_score"])
                    baseline_rms = max(best_hotword.model.avg_rms, 1e-6)
                    window_rms = rms(best_window or [])
                    min_rms = baseline_rms * tuning["min_rms_factor"]
                    if best_score >= effective_threshold and window_rms >= min_rms:
                        required_hits = tuning["required_hits"]
                        current_hits = consecutive_hits.get(best_hotword.id, 0) + 1
                        consecutive_hits = {best_hotword.id: current_hits}
                        if current_hits < required_hits:
                            continue
                        return TriggerEvent(
                            source="local",
                            message=(
                                f"Detected local wakeword '{best_hotword.label}' "
                                f"with score {best_score:.3f} (threshold {effective_threshold:.3f}, hits {current_hits}/{required_hits})"
                            ),
                            hotword_id=best_hotword.id,
                            hotword_label=best_hotword.label,
                            score=best_score,
                        )
                    consecutive_hits = {}
                else:
                    consecutive_hits = {}
        except LocalAudioStreamError as exc:
            raise RuntimeError(f"Failed to read local audio stream: {exc}") from exc
        finally:
            if self._audio_stream is not None:
                self._audio_stream.stop()

        return None

    def request_manual_trigger(self) -> bool:
        self._manual_trigger.set()
        return True

    def reload_hotwords(self, hotwords: list[HotwordResponse]) -> list[str]:
        if self._audio_stream is not None:
            self._audio_stream.stop()
            self._audio_stream = None
        self._loaded_hotwords = self._load_runtime_hotwords(hotwords)
        return self.active_hotwords()

    def active_hotwords(self) -> list[str]:
        return [hotword.id for hotword in self._loaded_hotwords]

    def active_hotword_count(self) -> int:
        return len(self._loaded_hotwords)

    def set_input_device_name(self, device_name: str) -> None:
        os.environ["HOTWORD_RUNTIME_DEVICE_NAME"] = (device_name or "").strip()
        if self._audio_stream is not None:
            self._audio_stream.stop()
            self._audio_stream = None

    def _load_runtime_hotwords(self, hotwords: list[HotwordResponse]) -> list[LoadedLocalHotword]:
        loaded_hotwords: list[LoadedLocalHotword] = []
        for hotword in hotwords:
            if hotword.engine_type != self.engine_type:
                continue
            if not hotword.model_path:
                raise RuntimeError(f"Local hotword '{hotword.id}' has no model_path configured")
            model_path = Path(hotword.model_path)
            if not model_path.exists():
                raise RuntimeError(f"Local hotword '{hotword.id}' model file does not exist: {model_path}")
            if model_path.suffix.lower() != ".json":
                raise RuntimeError(
                    f"Local hotword '{hotword.id}' expects a JSON model artifact, got: {model_path.suffix}"
                )
            try:
                model = load_local_model(model_path)
            except ValueError as exc:
                raise RuntimeError(f"Failed to load local model for '{hotword.id}': {exc}") from exc
            if model.hotword_id != hotword.id:
                raise RuntimeError(
                    f"Local model hotword_id mismatch for '{hotword.id}': model contains '{model.hotword_id}'"
                )
            loaded_hotwords.append(
                LoadedLocalHotword(
                    runtime_hotword=RuntimeHotword(
                        id=hotword.id,
                        label=hotword.label,
                        phrase=hotword.phrase,
                        engine_type=hotword.engine_type,
                        model_path=str(model_path),
                        sensitivity=_resolve_threshold(hotword),
                    ),
                    model=model,
                )
            )
        return loaded_hotwords

    def _ensure_audio_stream(self, sample_rate: int) -> None:
        if self._audio_stream is None:
            runtime_device_name = os.getenv(
                "HOTWORD_RUNTIME_DEVICE_NAME",
                settings.hotword_runtime_device_name,
            )
            self._audio_stream = LocalAudioStream(
                sample_rate=sample_rate,
                channels=1,
                device_index=settings.hotword_runtime_device_index,
                device_name=runtime_device_name or "",
            )

    @staticmethod
    def _runtime_tuning() -> dict[str, float | int]:
        def _clamp_float(value: str | None, fallback: float, min_value: float, max_value: float) -> float:
            try:
                parsed = float(value) if value is not None and str(value).strip() != "" else fallback
            except (TypeError, ValueError):
                parsed = fallback
            return max(min_value, min(max_value, parsed))

        def _clamp_int(value: str | None, fallback: int, min_value: int, max_value: int) -> int:
            try:
                parsed = int(value) if value is not None and str(value).strip() != "" else fallback
            except (TypeError, ValueError):
                parsed = fallback
            return max(min_value, min(max_value, parsed))

        return {
            "input_gain": _clamp_float(
                os.getenv("HOTWORD_RUNTIME_INPUT_GAIN"),
                settings.hotword_runtime_input_gain,
                0.1,
                8.0,
            ),
            "min_score": _clamp_float(
                os.getenv("HOTWORD_RUNTIME_MIN_SCORE"),
                settings.hotword_runtime_min_score,
                0.0,
                1.0,
            ),
            "min_rms_factor": _clamp_float(
                os.getenv("HOTWORD_RUNTIME_MIN_RMS_FACTOR"),
                settings.hotword_runtime_min_rms_factor,
                0.0,
                2.0,
            ),
            "required_hits": _clamp_int(
                os.getenv("HOTWORD_RUNTIME_REQUIRED_HITS"),
                settings.hotword_runtime_required_hits,
                1,
                10,
            ),
        }


class PorcupineAdapter:
    engine_type = "porcupine"

    def __init__(self) -> None:
        self._manual_trigger = Event()
        self._active_hotwords: list[RuntimeHotword] = []
        self._porcupine = None
        self._recorder = None

    def build_model(self, hotword: HotwordResponse, sample_paths: list[Path]) -> dict[str, object]:
        if hotword.model_path:
            return {
                "engine_type": self.engine_type,
                "message": "Legacy Porcupine model is already imported",
                "model_ready": True,
            }
        raise ValueError("Porcupine hotwords require an imported .ppn model file")

    def detect(self, file_path: Path, hotwords: list[HotwordResponse]) -> tuple[HotwordResponse | None, str]:
        runtime_hotwords = self._to_runtime_hotwords(hotwords)
        if not runtime_hotwords:
            return None, "No active Porcupine hotwords configured"

        porcupine = self._create_porcupine(runtime_hotwords)
        try:
            samples = self._read_wav_samples(file_path, porcupine.sample_rate)
            if not samples:
                return None, "Audio file is empty"
            best_match_index = None
            for frame in self._iter_frames(samples, porcupine.frame_length):
                result = porcupine.process(frame)
                if result >= 0:
                    best_match_index = result
                    break
            if best_match_index is None:
                return None, "No Porcupine match detected in audio file"
            matched_hotword = next(
                (hotword for hotword in hotwords if hotword.id == runtime_hotwords[best_match_index].id),
                None,
            )
            if matched_hotword is None:
                return None, "Matched Porcupine hotword is not available"
            return matched_hotword, f"Porcupine matched '{matched_hotword.id}'"
        finally:
            porcupine.delete()

    def wait_for_trigger(self, stop_event: Event, poll_interval: float = 0.5) -> TriggerEvent | None:
        if self._manual_trigger.is_set():
            self._manual_trigger.clear()
            return TriggerEvent(source="manual", message="Manual runtime trigger received")

        if not self._active_hotwords:
            stop_event.wait(timeout=poll_interval)
            return None

        self._ensure_runtime_ready()
        assert self._porcupine is not None
        assert self._recorder is not None

        self._recorder.start()
        try:
            while not stop_event.is_set():
                if self._manual_trigger.is_set():
                    self._manual_trigger.clear()
                    return TriggerEvent(source="manual", message="Manual runtime trigger received")
                pcm = self._recorder.read()
                keyword_index = self._porcupine.process(pcm)
                if keyword_index >= 0:
                    hotword = self._active_hotwords[keyword_index]
                    return TriggerEvent(
                        source="porcupine",
                        message=f"Detected wakeword '{hotword.label}'",
                        hotword_id=hotword.id,
                        hotword_label=hotword.label,
                        score=hotword.sensitivity,
                    )
        finally:
            self._recorder.stop()

        return None

    def request_manual_trigger(self) -> bool:
        self._manual_trigger.set()
        return True

    def reload_hotwords(self, hotwords: list[HotwordResponse]) -> list[str]:
        self._cleanup_runtime()
        self._active_hotwords = self._to_runtime_hotwords(hotwords)
        if not self._active_hotwords:
            return []
        self._porcupine = self._create_porcupine(self._active_hotwords)
        self._recorder = self._create_recorder(self._porcupine.frame_length)
        return self.active_hotwords()

    def active_hotwords(self) -> list[str]:
        return [hotword.id for hotword in self._active_hotwords]

    def active_hotword_count(self) -> int:
        return len(self._active_hotwords)

    def _to_runtime_hotwords(self, hotwords: list[HotwordResponse]) -> list[RuntimeHotword]:
        runtime_hotwords: list[RuntimeHotword] = []
        for hotword in hotwords:
            if hotword.engine_type != self.engine_type:
                continue
            if not hotword.model_path:
                continue
            model_path = Path(hotword.model_path)
            if not model_path.exists() or model_path.suffix.lower() != ".ppn":
                continue
            runtime_hotwords.append(
                RuntimeHotword(
                    id=hotword.id,
                    label=hotword.label,
                    phrase=hotword.phrase,
                    engine_type=hotword.engine_type,
                    model_path=str(model_path),
                    sensitivity=_resolve_threshold(hotword),
                )
            )
        return runtime_hotwords

    def _create_porcupine(self, runtime_hotwords: list[RuntimeHotword]):
        if not settings.hotword_access_key:
            raise RuntimeError("HOTWORD_ACCESS_KEY is required for Porcupine runtime")
        if not runtime_hotwords:
            raise RuntimeError("No active Porcupine hotwords configured")

        import pvporcupine

        try:
            return pvporcupine.create(
                access_key=settings.hotword_access_key,
                keyword_paths=[hotword.model_path for hotword in runtime_hotwords],
                sensitivities=[hotword.sensitivity for hotword in runtime_hotwords],
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize Porcupine: {exc}") from exc

    def _create_recorder(self, frame_length: int):
        try:
            from pvrecorder import PvRecorder
            return PvRecorder(
                frame_length=frame_length,
                device_index=settings.hotword_runtime_device_index,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize PvRecorder: {exc}") from exc

    def _ensure_runtime_ready(self) -> None:
        if self._porcupine is None or self._recorder is None:
            raise RuntimeError("Porcupine runtime is not loaded")

    def _cleanup_runtime(self) -> None:
        if self._recorder is not None:
            try:
                self._recorder.delete()
            except Exception:
                pass
            self._recorder = None
        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None

    def _read_wav_samples(self, file_path: Path, expected_sample_rate: int) -> list[int]:
        try:
            with wave.open(str(file_path), "rb") as wav_file:
                if wav_file.getframerate() != expected_sample_rate:
                    raise ValueError(
                        f"expected {expected_sample_rate} Hz WAV, got {wav_file.getframerate()} Hz"
                    )
                if wav_file.getsampwidth() != 2:
                    raise ValueError("expected 16-bit PCM WAV input")
                if wav_file.getnchannels() != 1:
                    raise ValueError("expected mono WAV input")
                raw_audio = wav_file.readframes(wav_file.getnframes())
                return list(struct.unpack("<" + "h" * (len(raw_audio) // 2), raw_audio))
        except wave.Error as exc:
            raise ValueError(
                "audio file is not a valid WAV/RIFF file; use 16-bit PCM WAV for Porcupine detection"
            ) from exc

    def _iter_frames(self, samples: list[int], frame_length: int):
        for start in range(0, len(samples), frame_length):
            frame = samples[start:start + frame_length]
            if len(frame) < frame_length:
                frame = frame + ([0] * (frame_length - len(frame)))
            yield frame


def _resolve_threshold(hotword: HotwordResponse) -> float:
    if hotword.threshold_override is not None:
        return hotword.threshold_override
    if hotword.sensitivity is not None:
        return hotword.sensitivity
    return settings.hotword_default_sensitivity


def get_engine_adapter(engine_name: str) -> HotwordEngineAdapter:
    if engine_name == "local":
        return LocalEngineAdapter()
    if engine_name == "placeholder":
        return PlaceholderEngineAdapter()
    if engine_name == "porcupine":
        return PorcupineAdapter()
    if engine_name == "openwakeword":
        return OpenWakeWordLegacyAdapter()
    raise ValueError(f"unsupported hotword engine: {engine_name}")
