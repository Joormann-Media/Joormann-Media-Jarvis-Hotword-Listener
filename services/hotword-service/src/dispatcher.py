from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class DispatchResult:
    status: str
    message: str
    input_transcript: str | None = None
    speaker_id: str | None = None
    response_audio_file: str | None = None


class VoiceCommandDispatcher:
    def __init__(self, dispatch_url: str, autoplay_response: bool) -> None:
        self._dispatch_url = dispatch_url
        self._autoplay_response = autoplay_response

    def dispatch(self, file_path: str) -> DispatchResult:
        payload = {"file_path": file_path}
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=3.0, read=60.0, write=10.0, pool=3.0)) as client:
                response = client.post(self._dispatch_url, json=payload)
        except httpx.TimeoutException as exc:
            return DispatchResult(status="timeout", message=f"Dispatch timeout: {exc}")
        except httpx.HTTPError as exc:
            return DispatchResult(status="error", message=f"Dispatch failed: {exc}")

        try:
            data = response.json()
        except ValueError:
            data = None

        if response.status_code >= 400:
            detail = None
            if isinstance(data, dict):
                detail = data.get("detail") or data.get("error")
            return DispatchResult(
                status=f"http_{response.status_code}",
                message=detail or "core-api returned an unexpected response",
            )

        if not isinstance(data, dict):
            return DispatchResult(
                status="invalid_response",
                message="core-api returned non-JSON response",
            )

        speaker = data.get("speaker") or {}
        speech = data.get("speech") or {}
        transcript = self._extract_transcript(data)
        return DispatchResult(
            status=data.get("status", "ok"),
            message=(
                "Voice command dispatched successfully"
                if transcript
                else "Voice command dispatched, but transcript is empty"
            ),
            input_transcript=transcript,
            speaker_id=speaker.get("speaker_id"),
            response_audio_file=speech.get("file_path"),
        )

    @staticmethod
    def _extract_transcript(data: dict) -> str | None:
        candidates = [
            data.get("input"),
            data.get("transcript"),
            data.get("text"),
            (data.get("stt") or {}).get("transcript") if isinstance(data.get("stt"), dict) else None,
            (data.get("result") or {}).get("transcript") if isinstance(data.get("result"), dict) else None,
            (data.get("result") or {}).get("text") if isinstance(data.get("result"), dict) else None,
        ]
        for value in candidates:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None
