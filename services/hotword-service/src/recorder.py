import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .audio_devices import detect_capture_devices


class RecorderError(RuntimeError):
    pass


class AudioRecorder:
    def __init__(
        self,
        recordings_dir: Path,
        record_seconds: int,
        device_index: int,
        device_name: str,
        sample_rate: int,
        use_arecord: bool,
    ) -> None:
        self._recordings_dir = recordings_dir
        self._record_seconds = record_seconds
        self._device_index = device_index
        self._device_name = device_name.strip()
        self._sample_rate = sample_rate
        self._use_arecord = use_arecord

    def record(self, record_seconds_override: int | None = None) -> Path:
        if not self._use_arecord:
            raise RecorderError("Only arecord follow-up recording is currently enabled")
        if shutil.which("arecord") is None:
            raise RecorderError("arecord is not available on this system")

        self._recordings_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        destination = self._recordings_dir / f"wake_{timestamp}.wav"
        record_seconds = (
            max(1, int(record_seconds_override))
            if record_seconds_override is not None
            else self._record_seconds
        )

        base_command = [
            "arecord",
            "-q",
            "-f",
            "S16_LE",
            "-r",
            str(self._sample_rate),
            "-c",
            "1",
            "-d",
            str(record_seconds),
        ]

        errors: list[str] = []
        for device in self._candidate_devices():
            command = list(base_command)
            if device is not None:
                command.extend(["-D", device])
            command.append(str(destination))
            try:
                subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=max(10, record_seconds + 5),
                )
                return destination
            except subprocess.TimeoutExpired as exc:
                errors.append(f"{device or 'default'}: timed out")
                continue
            except subprocess.CalledProcessError as exc:
                detail = exc.stderr.strip() or exc.stdout.strip() or "arecord failed"
                errors.append(f"{device or 'default'}: {detail}")
                continue

        detail = "; ".join(errors) if errors else "arecord failed"
        raise RecorderError(detail)

    def set_device_name(self, device_name: str) -> None:
        self._device_name = (device_name or "").strip()

    def _candidate_devices(self) -> Iterable[str | None]:
        seen: set[str | None] = set()

        def add(device: str | None) -> None:
            if device in seen:
                return
            seen.add(device)
            candidates.append(device)

        candidates: list[str | None] = []
        if self._device_name:
            add(self._device_name)
        if self._device_index >= 0:
            add(f"plughw:{self._device_index},0")
            add(f"hw:{self._device_index},0")
        for detected in detect_capture_devices():
            add(detected)
        add(None)  # system default
        add("pulse")
        add("sysdefault")
        return candidates
