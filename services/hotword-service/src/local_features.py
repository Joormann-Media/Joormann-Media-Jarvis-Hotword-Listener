import math
import struct
import wave
from pathlib import Path


def pcm16_bytes_to_floats(raw_audio: bytes) -> list[float]:
    if not raw_audio:
        return []
    pcm = struct.unpack("<" + "h" * (len(raw_audio) // 2), raw_audio)
    return [sample / 32768.0 for sample in pcm]


def read_wav_floats(file_path: Path) -> tuple[list[float], int]:
    try:
        with wave.open(str(file_path), "rb") as wav_file:
            if wav_file.getsampwidth() != 2:
                raise ValueError("expected 16-bit PCM WAV input")
            if wav_file.getnchannels() != 1:
                raise ValueError("expected mono WAV input")
            sample_rate = wav_file.getframerate()
            raw_audio = wav_file.readframes(wav_file.getnframes())
        return pcm16_bytes_to_floats(raw_audio), sample_rate
    except wave.Error as exc:
        raise ValueError(
            "audio file is not a valid WAV/RIFF file; use 16-bit PCM WAV for local detection"
        ) from exc


def sample_feature_vector(samples: list[float], bins: int = 64) -> list[float]:
    if not samples:
        return [0.0] * bins

    chunk_size = max(1, math.ceil(len(samples) / bins))
    features: list[float] = []
    for start in range(0, len(samples), chunk_size):
        window = samples[start:start + chunk_size]
        features.append(sum(abs(value) for value in window) / len(window))
        if len(features) == bins:
            break

    if len(features) < bins:
        features.extend([0.0] * (bins - len(features)))
    return features


def rms(samples: list[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(value * value for value in samples) / len(samples))


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return max(-1.0, min(1.0, numerator / (left_norm * right_norm)))
