import logging
import os
import shutil
from datetime import timedelta
from pathlib import Path
from threading import Event, Lock, Thread

from .audio_devices import detect_capture_devices, detect_runtime_audio_options
from .config import SERVICE_DIR, settings
from .dispatcher import VoiceCommandDispatcher
from .engine_adapter import TriggerEvent, get_engine_adapter
from .listener import HotwordListener
from .local_features import read_wav_floats, rms
from .recorder import AudioRecorder, RecorderError
from .schemas import (
    AudioDeviceOptionResponse,
    RuntimeAudioDevicesResponse,
    RuntimeAudioProbeResponse,
    RuntimeAudioTuningResponse,
    RuntimeConfigResponse,
    RuntimeControlResponse,
    RuntimeStatusResponse,
    RuntimeTriggerResponse,
)
from .state import runtime_state, utc_now
from .storage import list_runtime_hotwords


def get_runtime_logger() -> logging.Logger:
    logger = logging.getLogger("jarvis.hotword.runtime")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    log_file = settings.runtime_log_file.resolve()
    if not any(
        isinstance(handler, logging.FileHandler) and handler.baseFilename == str(log_file)
        for handler in logger.handlers
    ):
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if settings.hotword_runtime_log_to_stdout and not any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in logger.handlers
    ):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.propagate = False
    return logger


class HotwordRuntimeService:
    def __init__(self) -> None:
        self._logger = get_runtime_logger()
        self._engine = get_engine_adapter(settings.hotword_engine)
        self._recorder = AudioRecorder(
            recordings_dir=settings.hotword_runtime_recordings_dir,
            record_seconds=settings.hotword_runtime_record_seconds,
            device_index=settings.hotword_runtime_device_index,
            device_name=settings.hotword_runtime_device_name,
            sample_rate=settings.hotword_runtime_followup_sample_rate,
            use_arecord=settings.hotword_followup_use_arecord,
        )
        self._dispatcher = VoiceCommandDispatcher(
            dispatch_url=settings.hotword_runtime_dispatch_url,
            autoplay_response=settings.hotword_runtime_autoplay_response,
        )
        self._configured_enabled = settings.hotword_listener_enabled
        self._device_name = settings.hotword_runtime_device_name.strip()
        self._input_gain = max(0.1, min(8.0, settings.hotword_runtime_input_gain))
        self._min_score = max(0.0, min(1.0, settings.hotword_runtime_min_score))
        self._min_rms_factor = max(0.0, min(2.0, settings.hotword_runtime_min_rms_factor))
        self._required_hits = max(1, min(10, settings.hotword_runtime_required_hits))
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._lock = Lock()

    def ensure_directories(self) -> None:
        settings.hotword_runtime_recordings_dir.mkdir(parents=True, exist_ok=True)
        settings.runtime_log_file.parent.mkdir(parents=True, exist_ok=True)
        settings.runtime_state_file.parent.mkdir(parents=True, exist_ok=True)

    def startup(self) -> None:
        self.ensure_directories()
        self.reload_hotwords(update_message=False)
        runtime_state.update(
            listener_running=False,
            message="Hotword listener is idle",
            speaking_active=False,
        )
        if self._configured_enabled:
            self.start()

    def shutdown(self) -> None:
        self.stop()

    def status(self) -> RuntimeStatusResponse:
        snapshot = runtime_state.read()
        now = utc_now()
        speaking_active = runtime_state.is_speaking_active(now)
        if speaking_active != snapshot.speaking_active:
            snapshot = runtime_state.update(speaking_active=speaking_active)
        cooldown_active = runtime_state.is_cooldown_active(now)
        return RuntimeStatusResponse(
            service=settings.service_name,
            status="ok",
            engine=settings.hotword_engine,
            listener_running=snapshot.listener_running,
            running=snapshot.listener_running,
            configured_enabled=self._configured_enabled,
            cooldown_active=cooldown_active,
            ignore_while_speaking=settings.hotword_runtime_ignore_while_speaking,
            speaking_active=snapshot.speaking_active,
            message=snapshot.message,
            device_index=settings.hotword_runtime_device_index,
            device_name=self._device_name or None,
            followup_sample_rate=settings.hotword_runtime_followup_sample_rate,
            default_sensitivity=settings.hotword_default_sensitivity,
            active_hotwords=list(snapshot.active_hotwords or []),
            active_hotword_count=len(snapshot.active_hotwords or []),
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
        )

    def config(self) -> RuntimeConfigResponse:
        hotwords = list_runtime_hotwords()
        return RuntimeConfigResponse(
            service=settings.service_name,
            status="ok",
            engine=settings.hotword_engine,
            listener_enabled=self._configured_enabled,
            device_index=settings.hotword_runtime_device_index,
            access_key_configured=bool(settings.hotword_access_key),
            cooldown_seconds=settings.hotword_runtime_cooldown_seconds,
            record_seconds=settings.hotword_runtime_record_seconds,
            followup_sample_rate=settings.hotword_runtime_followup_sample_rate,
            followup_use_arecord=settings.hotword_followup_use_arecord,
            device_name=self._device_name or None,
            dispatch_url=settings.hotword_runtime_dispatch_url,
            ignore_while_speaking=settings.hotword_runtime_ignore_while_speaking,
            default_sensitivity=settings.hotword_default_sensitivity,
            active_hotwords=[
                {
                    "id": hotword.id,
                    "label": hotword.label,
                    "phrase": hotword.phrase,
                    "engine_type": hotword.engine_type,
                    "model_path": hotword.model_path,
                    "sensitivity": hotword.sensitivity,
                    "runtime_enabled": hotword.runtime_enabled,
                    "speaker_ids": hotword.speaker_ids,
                    "model_ready": hotword.model_ready,
                    "priority": hotword.priority,
                    "is_default": hotword.is_default,
                }
                for hotword in hotwords
            ],
        )

    def configure_listener_enabled(self, enabled: bool) -> RuntimeControlResponse:
        enabled = bool(enabled)
        try:
            self._persist_env_value("HOTWORD_LISTENER_ENABLED", "1" if enabled else "0")
        except OSError as exc:
            message = f"Listener-Autostart konnte nicht gespeichert werden: {exc}"
            runtime_state.update(message=message)
            return self._control_response(message=message)

        self._configured_enabled = enabled

        running = self._thread is not None and self._thread.is_alive()
        if enabled:
            if running:
                message = "Listener-Autostart aktiviert. Runtime laeuft bereits."
                runtime_state.update(message=message)
                return self._control_response(message=message)
            self.start()
            return self._control_response(
                message="Listener-Autostart aktiviert. Runtime gestartet.",
            )

        if running:
            self.stop()
            return self._control_response(
                message="Listener-Autostart deaktiviert. Runtime gestoppt.",
            )

        message = "Listener-Autostart deaktiviert."
        runtime_state.update(message=message)
        return self._control_response(message=message)

    def list_audio_devices(self) -> RuntimeAudioDevicesResponse:
        options: list[AudioDeviceOptionResponse] = [
            AudioDeviceOptionResponse(value=value, label=label)
            for value, label in detect_runtime_audio_options()
        ]
        configured = self._device_name or ""
        if configured and not any(item.value == configured for item in options):
            options.append(
                AudioDeviceOptionResponse(
                    value=configured,
                    label=f"Gespeichertes Mikrofon ({configured})",
                )
            )
        return RuntimeAudioDevicesResponse(
            service=settings.service_name,
            status="ok",
            configured_device_name=self._device_name or None,
            devices=options,
        )

    def configure_audio_input(self, device_name: str | None) -> RuntimeControlResponse:
        normalized = (device_name or "").strip()
        self._persist_env_value("HOTWORD_RUNTIME_DEVICE_NAME", normalized)
        os.environ["HOTWORD_RUNTIME_DEVICE_NAME"] = normalized
        self._device_name = normalized
        if hasattr(self._recorder, "set_device_name"):
            self._recorder.set_device_name(normalized)
        if hasattr(self._engine, "set_input_device_name"):
            self._engine.set_input_device_name(normalized)

        running = self._thread is not None and self._thread.is_alive()
        if running:
            self.stop()
            self.start()
            message = (
                f"Runtime-Mikro als Standard gespeichert: '{normalized or 'default'}' "
                "(Listener neu gestartet)."
            )
            return self._control_response(message=message)

        message = f"Runtime-Mikro als Standard gespeichert: '{normalized or 'default'}'."
        runtime_state.update(message=message)
        return self._control_response(message=message)

    def audio_probe(self, seconds: int = 3) -> RuntimeAudioProbeResponse:
        record_seconds = max(1, min(10, int(seconds)))
        probes_dir = settings.hotword_runtime_recordings_dir / "_probes"
        probes_dir.mkdir(parents=True, exist_ok=True)

        was_running = self._thread is not None and self._thread.is_alive()
        if was_running:
            self.stop()

        try:
            raw_file = self._recorder.record(record_seconds_override=record_seconds)
        except RecorderError as exc:
            if was_running:
                self.start()
            raise RuntimeError(f"Runtime audio probe failed: {exc}") from exc

        probe_name = f"probe_{utc_now().strftime('%Y%m%d_%H%M%S')}.wav"
        probe_file = probes_dir / probe_name
        try:
            shutil.move(str(raw_file), str(probe_file))
        except OSError:
            probe_file = raw_file

        try:
            samples, sample_rate = read_wav_floats(probe_file)
        except ValueError as exc:
            if was_running:
                self.start()
            raise RuntimeError(f"Runtime audio probe parse failed: {exc}") from exc

        signal_rms = rms(samples)
        signal_peak = max((abs(value) for value in samples), default=0.0)
        detected = signal_rms >= 0.003 or signal_peak >= 0.02

        if was_running:
            self.start()

        return RuntimeAudioProbeResponse(
            service=settings.service_name,
            status="ok",
            seconds=record_seconds,
            sample_rate=sample_rate,
            sample_count=len(samples),
            rms=signal_rms,
            peak=signal_peak,
            detected_signal=detected,
            device_name=self._device_name or None,
            file_name=probe_file.name,
            file_path=str(probe_file),
            playback_url=f"/runtime/audio-probe/{probe_file.name}",
            message=(
                "Signal erkannt."
                if detected
                else "Kein brauchbares Signal erkannt. Prüfe Runtime-Mikro und System-Eingangslautstärke."
            ),
        )

    def get_audio_tuning(self) -> RuntimeAudioTuningResponse:
        return RuntimeAudioTuningResponse(
            service=settings.service_name,
            status="ok",
            input_gain=self._input_gain,
            min_score=self._min_score,
            min_rms_factor=self._min_rms_factor,
            required_hits=self._required_hits,
            message="Runtime audio tuning loaded",
        )

    def configure_audio_tuning(
        self,
        input_gain: float | None = None,
        min_score: float | None = None,
        min_rms_factor: float | None = None,
        required_hits: int | None = None,
    ) -> RuntimeAudioTuningResponse:
        if input_gain is not None:
            self._input_gain = max(0.1, min(8.0, float(input_gain)))
            self._persist_env_value("HOTWORD_RUNTIME_INPUT_GAIN", f"{self._input_gain:.3f}")
        if min_score is not None:
            self._min_score = max(0.0, min(1.0, float(min_score)))
            self._persist_env_value("HOTWORD_RUNTIME_MIN_SCORE", f"{self._min_score:.3f}")
        if min_rms_factor is not None:
            self._min_rms_factor = max(0.0, min(2.0, float(min_rms_factor)))
            self._persist_env_value("HOTWORD_RUNTIME_MIN_RMS_FACTOR", f"{self._min_rms_factor:.3f}")
        if required_hits is not None:
            self._required_hits = max(1, min(10, int(required_hits)))
            self._persist_env_value("HOTWORD_RUNTIME_REQUIRED_HITS", str(self._required_hits))

        os.environ["HOTWORD_RUNTIME_INPUT_GAIN"] = str(self._input_gain)
        os.environ["HOTWORD_RUNTIME_MIN_SCORE"] = str(self._min_score)
        os.environ["HOTWORD_RUNTIME_MIN_RMS_FACTOR"] = str(self._min_rms_factor)
        os.environ["HOTWORD_RUNTIME_REQUIRED_HITS"] = str(self._required_hits)

        message = (
            "Audio tuning gespeichert: "
            f"gain={self._input_gain:.2f}, min_score={self._min_score:.2f}, "
            f"min_rms={self._min_rms_factor:.2f}, hits={self._required_hits}"
        )
        runtime_state.update(message=message)
        return RuntimeAudioTuningResponse(
            service=settings.service_name,
            status="ok",
            input_gain=self._input_gain,
            min_score=self._min_score,
            min_rms_factor=self._min_rms_factor,
            required_hits=self._required_hits,
            message=message,
        )

    def reload_hotwords(self, update_message: bool = True) -> RuntimeControlResponse | list[str]:
        try:
            active_hotwords = self._engine.reload_hotwords(list_runtime_hotwords())
        except Exception as exc:
            self._logger.exception("Failed to reload runtime hotwords")
            runtime_state.update(
                active_hotwords=[],
                message=f"Failed to reload runtime hotwords: {exc}",
            )
            if not update_message:
                raise
            return self._control_response(
                message=f"Failed to reload runtime hotwords: {exc}"
            )
        runtime_state.update(active_hotwords=active_hotwords)
        self._logger.info("Loaded runtime hotwords: %s", ", ".join(active_hotwords) or "none")
        if not update_message:
            return active_hotwords
        message = (
            f"Reloaded {len(active_hotwords)} runtime hotword(s)"
            if active_hotwords
            else f"No active {settings.hotword_engine} hotwords configured"
        )
        runtime_state.update(message=message)
        return self._control_response(message=message)

    def start(self) -> RuntimeControlResponse:
        with self._lock:
            if self._thread and self._thread.is_alive():
                runtime_state.update(message="Hotword listener already running")
                return self._control_response()

            try:
                self.reload_hotwords(update_message=False)
            except Exception as exc:
                return self._control_response(
                    message=f"Hotword listener could not start: {exc}"
                )
            self._stop_event = Event()
            listener = HotwordListener(
                engine=self._engine,
                stop_event=self._stop_event,
                on_trigger=self._handle_trigger,
                on_error=self._handle_listener_error,
                logger=self._logger,
            )
            self._thread = Thread(
                target=listener.run,
                name="hotword-listener",
                daemon=True,
            )
            active_hotwords = list(runtime_state.read().active_hotwords or [])
            start_message = (
                f"Hotword listener started with engine '{settings.hotword_engine}'"
                if active_hotwords
                else f"Hotword listener started, but no active {settings.hotword_engine} hotwords are configured"
            )
            runtime_state.update(
                listener_running=True,
                last_started_at=utc_now(),
                message=start_message,
            )
            self._thread.start()
            self._logger.info("Hotword listener started")
            return self._control_response(message=start_message)

    def stop(self) -> RuntimeControlResponse:
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._stop_event.set()
                self._thread.join(timeout=2.0)
                if self._thread.is_alive():
                    runtime_state.update(
                        listener_running=True,
                        message="Stop requested, listener is finishing active work",
                    )
                    self._logger.info("Stop requested while listener was still busy")
                    return self._control_response(
                        message="Stop requested, listener is finishing active work"
                    )
                self._thread = None
            runtime_state.update(
                listener_running=False,
                last_stopped_at=utc_now(),
                message="Hotword listener stopped",
            )
            self._logger.info("Hotword listener stopped")
            return self._control_response(message="Hotword listener stopped")

    def test_trigger(self) -> RuntimeTriggerResponse:
        running = self._thread is not None and self._thread.is_alive()
        if not running:
            runtime_state.update(message="Listener is not running")
            return self._trigger_response(
                trigger_accepted=False,
                message="Listener is not running",
            )

        accepted = self._engine.request_manual_trigger()
        message = "Manual runtime trigger queued" if accepted else "Manual trigger rejected"
        runtime_state.update(message=message)
        return self._trigger_response(trigger_accepted=accepted, message=message)

    def _handle_listener_error(self, message: str) -> None:
        runtime_state.update(message=message)

    @staticmethod
    def _is_empty_transcript(dispatch_status: str, dispatch_message: str) -> bool:
        status_text = (dispatch_status or "").lower()
        message_text = (dispatch_message or "").lower()
        return (
            "empty_transcript" in status_text
            or "transcript is empty" in message_text
            or "transcript is empty" in status_text
        )

    def _handle_trigger(self, trigger: TriggerEvent) -> None:
        self._logger.info(
            "HOTWORD DETECTED id=%s label=%s score=%s source=%s",
            trigger.hotword_id,
            trigger.hotword_label,
            trigger.score,
            trigger.source,
        )
        now = utc_now()
        if settings.hotword_runtime_ignore_while_speaking and runtime_state.is_speaking_active(now):
            runtime_state.update(
                speaking_active=True,
                message="Trigger ignored while speaking protection is active",
            )
            self._logger.info("Trigger ignored because speaking protection is active")
            return

        if runtime_state.is_cooldown_active(now):
            remaining = runtime_state.seconds_until_ready(now)
            runtime_state.update(
                message=f"Trigger ignored during cooldown ({remaining:.1f}s remaining)"
            )
            self._logger.info("Trigger ignored during cooldown (%.1fs remaining)", remaining)
            return

        runtime_state.update(
            last_triggered_at=now,
            last_detected_hotword=trigger.hotword_id or trigger.hotword_label,
            last_detection_score=trigger.score,
            last_dispatch_status=None,
            last_dispatch_message=None,
            last_input_transcript=None,
            last_speaker_id=None,
            last_response_audio_file=None,
            message=trigger.message,
        )

        try:
            recording_file = self._recorder.record()
        except RecorderError as exc:
            runtime_state.update(
                last_recording_file=None,
                last_dispatch_status="recording_error",
                last_dispatch_message=str(exc),
                message="Recording failed after wakeword trigger",
            )
            self._logger.error("Recording failed: %s", exc)
            return

        runtime_state.update(
            last_recording_file=str(recording_file),
            message="Recording completed, dispatching to core-api",
        )
        self._logger.info(
            "Recording saved to %s after hotword=%s score=%s",
            recording_file,
            trigger.hotword_id,
            trigger.score,
        )
        self._logger.info(
            "FORWARDING TO CORE/STT (Whisper pipeline) url=%s file=%s",
            settings.hotword_runtime_dispatch_url,
            recording_file,
        )

        dispatch_result = self._dispatcher.dispatch(str(recording_file))
        if (
            settings.hotword_runtime_retry_on_empty_transcript
            and self._is_empty_transcript(dispatch_result.status, dispatch_result.message)
        ):
            retry_seconds = settings.hotword_runtime_record_seconds + max(
                1, settings.hotword_runtime_retry_extra_seconds
            )
            runtime_state.update(
                message=(
                    f"Leeres Transcript erkannt, starte zweiten Record ({retry_seconds}s) ..."
                )
            )
            self._logger.info(
                "Empty transcript from dispatch. Retrying follow-up recording for %ss.",
                retry_seconds,
            )
            try:
                retry_recording_file = self._recorder.record(record_seconds_override=retry_seconds)
                runtime_state.update(
                    last_recording_file=str(retry_recording_file),
                    message="Zweiter Record abgeschlossen, dispatch erneut ...",
                )
                dispatch_result = self._dispatcher.dispatch(str(retry_recording_file))
            except RecorderError as exc:
                runtime_state.update(
                    last_dispatch_status="recording_retry_error",
                    last_dispatch_message=str(exc),
                    message="Zweiter Record fehlgeschlagen",
                )
                self._logger.error("Retry recording failed: %s", exc)
                return

        speaking_until = None
        speaking_active = False
        if settings.hotword_runtime_ignore_while_speaking and dispatch_result.status == "ok":
            speaking_until = utc_now() + timedelta(
                seconds=settings.hotword_runtime_speaking_guard_seconds
            )
            speaking_active = True

        runtime_state.update(
            speaking_until=speaking_until,
            speaking_active=speaking_active,
            last_dispatch_status=dispatch_result.status,
            last_dispatch_message=dispatch_result.message,
            last_input_transcript=dispatch_result.input_transcript,
            last_speaker_id=dispatch_result.speaker_id,
            last_response_audio_file=dispatch_result.response_audio_file,
            message="Dispatch completed" if dispatch_result.status == "ok" else "Dispatch finished with issues",
        )
        self._logger.info(
            "Dispatch status=%s hotword=%s transcript=%s speaker=%s response_audio=%s",
            dispatch_result.status,
            trigger.hotword_id,
            dispatch_result.input_transcript,
            dispatch_result.speaker_id,
            dispatch_result.response_audio_file,
        )
        if dispatch_result.input_transcript:
            self._logger.info("WHISPER TRANSCRIPT: %s", dispatch_result.input_transcript)
        else:
            self._logger.info("WHISPER TRANSCRIPT: <empty>")

    def _control_response(self, message: str | None = None) -> RuntimeControlResponse:
        payload = self.status().model_dump()
        if message is not None:
            payload["message"] = message
        return RuntimeControlResponse(**payload)

    def _trigger_response(self, trigger_accepted: bool, message: str) -> RuntimeTriggerResponse:
        payload = self.status().model_dump()
        payload["message"] = message
        return RuntimeTriggerResponse(
            **payload,
            trigger_accepted=trigger_accepted,
        )

    @staticmethod
    def _persist_env_value(key: str, value: str) -> None:
        env_path = Path(SERVICE_DIR) / ".env"
        line = f"{key}={value}"

        if not env_path.exists():
            env_path.write_text(f"{line}\n", encoding="utf-8")
            return

        lines = env_path.read_text(encoding="utf-8").splitlines()
        replaced = False
        for idx, raw in enumerate(lines):
            current = raw.strip()
            if not current or current.startswith("#") or "=" not in current:
                continue
            left = current.split("=", 1)[0].strip()
            if left == key:
                lines[idx] = line
                replaced = True
                break

        if not replaced:
            lines.append(line)

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


runtime_service = HotwordRuntimeService()


def initialize_runtime() -> None:
    runtime_service.startup()


def shutdown_runtime() -> None:
    runtime_service.shutdown()


def get_runtime_status() -> RuntimeStatusResponse:
    return runtime_service.status()


def get_runtime_config() -> RuntimeConfigResponse:
    return runtime_service.config()


def reload_runtime_hotwords() -> RuntimeControlResponse:
    response = runtime_service.reload_hotwords(update_message=True)
    assert isinstance(response, RuntimeControlResponse)
    return response


def start_runtime_listener() -> RuntimeControlResponse:
    return runtime_service.start()


def stop_runtime_listener() -> RuntimeControlResponse:
    return runtime_service.stop()


def test_runtime_trigger() -> RuntimeTriggerResponse:
    return runtime_service.test_trigger()


def configure_runtime_listener(enabled: bool) -> RuntimeControlResponse:
    return runtime_service.configure_listener_enabled(enabled)


def get_runtime_audio_tuning() -> RuntimeAudioTuningResponse:
    return runtime_service.get_audio_tuning()


def configure_runtime_audio_tuning(
    input_gain: float | None = None,
    min_score: float | None = None,
    min_rms_factor: float | None = None,
    required_hits: int | None = None,
) -> RuntimeAudioTuningResponse:
    return runtime_service.configure_audio_tuning(
        input_gain=input_gain,
        min_score=min_score,
        min_rms_factor=min_rms_factor,
        required_hits=required_hits,
    )


def get_runtime_audio_devices() -> RuntimeAudioDevicesResponse:
    return runtime_service.list_audio_devices()


def configure_runtime_audio_input(device_name: str | None) -> RuntimeControlResponse:
    return runtime_service.configure_audio_input(device_name)


def runtime_audio_probe(seconds: int = 3) -> RuntimeAudioProbeResponse:
    return runtime_service.audio_probe(seconds)
