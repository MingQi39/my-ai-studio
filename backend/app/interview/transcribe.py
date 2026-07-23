"""Interview oral-answer STT via DashScope Paraformer realtime (local file call)."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from dashscope.audio.asr import Recognition
except ImportError:  # pragma: no cover - optional until dashscope installed
    Recognition = None  # type: ignore[misc, assignment]


class SttConfigError(RuntimeError):
    """STT is not configured (missing API key or SDK)."""


class SttEmptyError(RuntimeError):
    """Upstream returned no usable transcript."""


class SttUpstreamError(RuntimeError):
    """Upstream Paraformer failed."""


def _extract_text(sentence: Any) -> str:
    if sentence is None:
        return ""
    if isinstance(sentence, dict):
        return str(sentence.get("text") or "").strip()
    if isinstance(sentence, list):
        parts: list[str] = []
        for item in sentence:
            if isinstance(item, dict):
                t = str(item.get("text") or "").strip()
                if t:
                    parts.append(t)
            elif item:
                parts.append(str(item).strip())
        return "".join(parts).strip()
    return str(sentence).strip()


def transcribe_audio_file(
    path: str,
    *,
    audio_format: str = "wav",
    language: str = "zh",
) -> str:
    """Transcribe a local audio file. Does not log transcript text."""
    api_key = (getattr(settings, "DASHSCOPE_API_KEY", "") or "").strip()
    if not api_key:
        raise SttConfigError("DASHSCOPE_API_KEY is not configured")
    if Recognition is None:
        raise SttConfigError("dashscope SDK is not installed")

    os.environ.setdefault("DASHSCOPE_API_KEY", api_key)
    model = (getattr(settings, "INTERVIEW_STT_MODEL", "") or "paraformer-realtime-v2").strip()
    sample_rate = int(getattr(settings, "INTERVIEW_STT_SAMPLE_RATE", 16000) or 16000)

    recognition = Recognition(
        model=model,
        format=audio_format,
        sample_rate=sample_rate,
        language_hints=[language] if language else ["zh"],
    )
    result = recognition.call(path)
    status = getattr(result, "status_code", None)
    if status is not None and int(status) != 200:
        message = getattr(result, "message", "upstream error") or "upstream error"
        logger.warning("interview_stt_upstream_error status=%s", status)
        raise SttUpstreamError(str(message))

    text = _extract_text(result.get_sentence() if hasattr(result, "get_sentence") else None)
    if not text:
        raise SttEmptyError("empty transcript")
    logger.info("interview_stt_ok chars=%s format=%s", len(text), audio_format)
    return text
