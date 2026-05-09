from __future__ import annotations

from pathlib import Path

from m_agent.api.chat_image_captioner import ChatImageCaptioner


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, payload: dict | None = None, text: str = "ok") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.reason = text

    def json(self) -> dict:
        return dict(self._payload)


def test_chat_image_captioner_api_mode_uses_json_field(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "tiny.png"
    image_path.write_bytes(b"fake-image")
    captured: dict = {}

    def _fake_post(url, headers=None, files=None, timeout=None, json=None):  # type: ignore[no-untyped-def]
        captured["url"] = url
        captured["headers"] = headers
        captured["files"] = files
        captured["timeout"] = timeout
        captured["json"] = json
        return _FakeResponse(payload={"blip_caption": "api generated caption"})

    import requests

    monkeypatch.setattr(requests, "post", _fake_post)
    captioner = ChatImageCaptioner(
        provider="api",
        api_url="https://caption.example.test/v1/caption",
        api_auth_token="secret-token",
    )

    caption = captioner.caption_image(image_path)

    assert caption == "api generated caption"
    assert captured["url"] == "https://caption.example.test/v1/caption"
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert "file" in captured["files"]


def test_chat_image_captioner_api_mode_supports_custom_field(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "tiny.png"
    image_path.write_bytes(b"fake-image")

    def _fake_post(url, headers=None, files=None, timeout=None, json=None):  # type: ignore[no-untyped-def]
        return _FakeResponse(payload={"caption_text": "custom field caption"})

    import requests

    monkeypatch.setattr(requests, "post", _fake_post)
    captioner = ChatImageCaptioner(
        provider="api",
        api_url="https://caption.example.test/v1/caption",
        api_caption_field="caption_text",
    )

    assert captioner.caption_image(image_path) == "custom field caption"


def test_chat_image_captioner_openai_mode_uses_openai_compatible_env(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "tiny.png"
    image_path.write_bytes(b"fake-image")

    captured: dict = {}

    class _FakeCompletions:
        def create(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["create_kwargs"] = kwargs
            message = type("Msg", (), {"content": "openai caption text"})()
            choice = type("Choice", (), {"message": message})()
            return type("Resp", (), {"choices": [choice]})()

    class _FakeChat:
        def __init__(self) -> None:
            self.completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["client_kwargs"] = kwargs
            self.chat = _FakeChat()

    class _FakeOpenAI:
        OpenAI = _FakeClient

    monkeypatch.setenv("API_SECRET_KEY", "project-secret")
    monkeypatch.setenv("BASE_URL", "https://openai-compatible.example/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    import sys

    monkeypatch.setitem(sys.modules, "openai", _FakeOpenAI)

    captioner = ChatImageCaptioner(provider="openai")
    caption = captioner.caption_image(image_path)

    assert caption == "openai caption text"
    assert captured["client_kwargs"]["api_key"] == "project-secret"
    assert captured["client_kwargs"]["base_url"] == "https://openai-compatible.example/v1"
    assert captured["create_kwargs"]["model"] == "gpt-4.1-mini"
    content = captured["create_kwargs"]["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
