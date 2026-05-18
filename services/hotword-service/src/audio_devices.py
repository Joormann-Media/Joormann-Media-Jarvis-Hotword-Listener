import re
import shutil
import subprocess
from dataclasses import dataclass


_CARD_LINE = re.compile(
    r"^(?:Karte|card)\s+(?P<card>\d+):\s*(?P<card_name>[^,\[]+).*?(?:Gerät|device)\s+(?P<device>\d+):\s*(?P<device_name>[^,\[]+)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class CaptureDeviceOption:
    score: int
    card_name: str
    device_name: str
    value: str
    label: str


def _score_device(card_name: str, device_name: str) -> int:
    text = f"{card_name} {device_name}".lower()
    score = 0
    if "usb" in text:
        score += 60
    if any(token in text for token in ("micro", "mic", "headset", "headphone")):
        score += 50
    if any(token in text for token in ("bluetooth", "blue", "bt")):
        score += 45
    if any(token in text for token in ("webcam", "camera")):
        score += 20
    if any(token in text for token in ("hdmi", "displayport", "dvi", "monitor")):
        score -= 40
    if "pch" in text:
        score -= 10
    return score


def _available_alsa_names() -> set[str]:
    if shutil.which("arecord") is None:
        return set()

    try:
        result = subprocess.run(
            ["arecord", "-L"],
            capture_output=True,
            text=True,
            timeout=2.5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()

    names: set[str] = set()
    for raw_line in result.stdout.splitlines():
        candidate = raw_line.strip()
        if not candidate or candidate.startswith(" "):
            continue
        names.add(candidate)
    return names


def _alsa_pcm_descriptions() -> dict[str, str]:
    if shutil.which("arecord") is None:
        return {}
    try:
        result = subprocess.run(
            ["arecord", "-L"],
            capture_output=True,
            text=True,
            timeout=2.5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}

    descriptions: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    for raw_line in result.stdout.splitlines():
        if raw_line.strip() and not raw_line.startswith(" "):
            if current_name and current_lines:
                descriptions[current_name] = " ".join(current_lines).strip()
            current_name = raw_line.strip()
            current_lines = []
            continue
        if current_name and raw_line.strip():
            current_lines.append(raw_line.strip())

    if current_name and current_lines:
        descriptions[current_name] = " ".join(current_lines).strip()

    return descriptions


def _find_card_description(card_name: str, device: str, descriptions: dict[str, str]) -> str | None:
    if not card_name:
        return None
    variants = {
        card_name,
        card_name.replace(" ", "_"),
        card_name.replace(" ", ""),
    }
    keys: list[str] = []
    for variant in variants:
        keys.extend(
            [
                f"sysdefault:CARD={variant}",
                f"hw:CARD={variant},DEV={device}",
                f"plughw:CARD={variant},DEV={device}",
                f"front:CARD={variant},DEV={device}",
            ]
        )
    for key in keys:
        detail = descriptions.get(key)
        if detail:
            return detail
    return None


def detect_capture_device_options() -> list[CaptureDeviceOption]:
    if shutil.which("arecord") is None:
        return []

    try:
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            timeout=2.5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    descriptions = _alsa_pcm_descriptions()
    ranked: list[CaptureDeviceOption] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        match = _CARD_LINE.search(line)
        if not match:
            continue
        card = match.group("card")
        device = match.group("device")
        card_name = match.group("card_name").strip()
        device_name = match.group("device_name").strip()
        score = _score_device(card_name, device_name)
        value = f"plughw:{card},{device}"
        detail = _find_card_description(card_name, device, descriptions)
        label_prefix = f"{card_name} / {device_name}"
        if detail:
            label_prefix = f"{label_prefix} - {detail}"
        label = f"{label_prefix} ({value})"
        ranked.append(
            CaptureDeviceOption(
                score=score,
                card_name=card_name,
                device_name=device_name,
                value=value,
                label=label,
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked


def detect_capture_devices() -> list[str]:
    return [item.value for item in detect_capture_device_options()]


def detect_runtime_audio_options() -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = [("", "Automatisch (default)")]
    available_names = _available_alsa_names()

    if "sysdefault" in available_names:
        options.append(("sysdefault", "Systemstandard ALSA (sysdefault)"))
    if "default" in available_names:
        options.append(("default", "ALSA Default (default)"))
    if "pulse" in available_names:
        options.append(("pulse", "PulseAudio / PipeWire (pulse)"))

    seen = {value for value, _ in options}
    for device in detect_capture_device_options():
        if device.value in seen:
            continue
        seen.add(device.value)
        options.append((device.value, device.label))

    return options
    devices: list[str] = []
    seen: set[str] = set()
    for _, device in ranked:
        if device in seen:
            continue
        seen.add(device)
        devices.append(device)
    return devices
