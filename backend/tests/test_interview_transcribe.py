"""Tests for interview oral-answer STT (Paraformer)."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.interview import router as interview_router
from app.interview import transcribe as transcribe_mod
from app.interview.transcribe import (
    SttConfigError,
    SttEmptyError,
    SttUpstreamError,
    transcribe_audio_file,
)


class _FakeResult:
    def __init__(self, status_code=200, sentence=None, message="ok"):
        self.status_code = status_code
        self.message = message
        self._sentence = sentence

    def get_sentence(self):
        return self._sentence


def test_transcribe_audio_file_returns_joined_text(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 44)

    class FakeRecognition:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def call(self, file: str):
            assert Path(file).exists()
            return _FakeResult(sentence=[{"text": "先说原理"}, {"text": "再说取舍"}])

    monkeypatch.setattr(transcribe_mod, "Recognition", FakeRecognition)
    monkeypatch.setattr(transcribe_mod.settings, "DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setattr(transcribe_mod.settings, "INTERVIEW_STT_MODEL", "paraformer-realtime-v2")

    text = transcribe_audio_file(str(audio), audio_format="wav")
    assert text == "先说原理再说取舍"


def test_transcribe_audio_file_requires_api_key(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 12)
    monkeypatch.setattr(transcribe_mod.settings, "DASHSCOPE_API_KEY", "")
    with pytest.raises(SttConfigError):
        transcribe_audio_file(str(audio), audio_format="wav")


def test_transcribe_audio_file_empty_raises(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 12)

    class FakeRecognition:
        def __init__(self, **kwargs):
            pass

        def call(self, file: str):
            return _FakeResult(sentence={"text": "  "})

    monkeypatch.setattr(transcribe_mod.settings, "DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setattr(transcribe_mod, "Recognition", FakeRecognition)
    with pytest.raises(SttEmptyError):
        transcribe_audio_file(str(audio), audio_format="wav")


def test_transcribe_audio_file_upstream_error(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 12)

    class FakeRecognition:
        def __init__(self, **kwargs):
            pass

        def call(self, file: str):
            return _FakeResult(status_code=500, message="boom", sentence=None)

    monkeypatch.setattr(transcribe_mod.settings, "DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setattr(transcribe_mod, "Recognition", FakeRecognition)
    with pytest.raises(SttUpstreamError):
        transcribe_audio_file(str(audio), audio_format="wav")


def test_stt_status_and_transcribe_endpoint(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(interview_router, prefix="/api/v1")

    async def fake_user():
        from uuid import uuid4

        return uuid4()

    from app.dependencies import get_current_user_auth

    app.dependency_overrides[get_current_user_auth] = fake_user
    client = TestClient(app)

    monkeypatch.setattr("app.api.v1.interview.settings.DASHSCOPE_API_KEY", "")
    assert client.get("/api/v1/interview/stt/status").json() == {"enabled": False}

    monkeypatch.setattr("app.api.v1.interview.settings.DASHSCOPE_API_KEY", "sk-test")
    assert client.get("/api/v1/interview/stt/status").json() == {"enabled": True}

    def fake_transcribe(path: str, audio_format: str = "wav", language: str = "zh") -> str:
        assert Path(path).exists()
        return "口述答案"

    monkeypatch.setattr("app.api.v1.interview.transcribe_audio_file", fake_transcribe)
    files = {"file": ("answer.wav", b"RIFF" + b"\x00" * 100, "audio/wav")}
    resp = client.post("/api/v1/interview/transcribe", files=files)
    assert resp.status_code == 200
    assert resp.json() == {"text": "口述答案"}

    empty = client.post(
        "/api/v1/interview/transcribe",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert empty.status_code == 400
