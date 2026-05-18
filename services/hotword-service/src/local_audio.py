import shutil
import subprocess
import time
from typing import Iterable

from .audio_devices import detect_capture_devices


class LocalAudioStreamError(RuntimeError):
    pass


class LocalAudioStream:
    def __init__(
        self,
        sample_rate: int,
        channels: int = 1,
        device_index: int = -1,
        device_name: str = "",
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._device_index = device_index
        self._device_name = device_name.strip()
        self._process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        if self._process is not None:
            return
        if shutil.which("arecord") is None:
            raise LocalAudioStreamError("arecord is not available on this system")

        base_command = [
            "arecord",
            "-q",
            "-t",
            "raw",
            "-f",
            "S16_LE",
            "-r",
            str(self._sample_rate),
            "-c",
            str(self._channels),
        ]

        errors: list[str] = []
        for device in self._candidate_devices():
            command = list(base_command)
            if device is not None:
                command.extend(["-D", device])
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except OSError as exc:
                errors.append(f"{device or 'default'}: {exc}")
                continue

            time.sleep(0.15)
            if process.poll() is not None:
                stderr = b""
                if process.stderr is not None:
                    stderr = process.stderr.read()
                detail = stderr.decode("utf-8", errors="ignore").strip() or "arecord exited immediately"
                errors.append(f"{device or 'default'}: {detail}")
                continue

            self._process = process
            return

        detail = "; ".join(errors) if errors else "failed to start arecord stream"
        raise LocalAudioStreamError(detail)

    def read(self, num_bytes: int) -> bytes:
        if self._process is None or self._process.stdout is None:
            raise LocalAudioStreamError("audio stream is not running")
        data = self._process.stdout.read(num_bytes)
        if not data:
            stderr = b""
            if self._process.stderr is not None:
                stderr = self._process.stderr.read1(4096)
            detail = stderr.decode("utf-8", errors="ignore").strip() or "arecord returned no data"
            raise LocalAudioStreamError(detail)
        return data

    def stop(self) -> None:
        if self._process is None:
            return
        try:
            self._process.terminate()
            self._process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=1.0)
        finally:
            self._process = None

    def _candidate_devices(self) -> Iterable[str | None]:
        seen: set[str | None] = set()
        candidates: list[str | None] = []

        def add(device: str | None) -> None:
            if device in seen:
                return
            seen.add(device)
            candidates.append(device)

        if self._device_name:
            add(self._device_name)
        if self._device_index >= 0:
            add(f"plughw:{self._device_index},0")
            add(f"hw:{self._device_index},0")
        for detected in detect_capture_devices():
            add(detected)
        add(None)
        add("pulse")
        add("sysdefault")
        return candidates
