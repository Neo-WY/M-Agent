from __future__ import annotations

import base64
import logging
import threading
from pathlib import Path
from typing import Any, Optional
import os

logger = logging.getLogger(__name__)


class ChatImageCaptioner:
    """Caption images via local BLIP or an external HTTP API."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        provider: str = "openai",
        model_name: str = "Salesforce/blip-image-captioning-base",
        device: Optional[str] = None,
        openai_model: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        api_url: Optional[str] = None,
        api_timeout_seconds: float = 30.0,
        api_auth_token: Optional[str] = None,
        api_auth_header: str = "Authorization",
        api_caption_field: str = "blip_caption",
        api_mode: str = "multipart",
    ) -> None:
        self.enabled = bool(enabled)
        self.provider = str(provider or "local").strip().lower() or "local"
        self.model_name = str(model_name or "Salesforce/blip-image-captioning-base").strip()
        self.device = str(device or "").strip() or None
        self.openai_model = str(openai_model or "").strip() or None
        self.openai_api_key = str(openai_api_key or "").strip() or None
        self.openai_base_url = str(openai_base_url or "").strip() or None
        self.api_url = str(api_url or "").strip() or None
        self.api_timeout_seconds = max(1.0, float(api_timeout_seconds or 30.0))
        self.api_auth_token = str(api_auth_token or "").strip() or None
        self.api_auth_header = str(api_auth_header or "Authorization").strip() or "Authorization"
        self.api_caption_field = str(api_caption_field or "blip_caption").strip() or "blip_caption"
        self.api_mode = str(api_mode or "multipart").strip().lower() or "multipart"
        self._lock = threading.Lock()
        self._processor: Any = None
        self._model: Any = None
        self._openai_client: Any = None
        self._load_error: Optional[str] = None

    def _ensure_local_model(self) -> tuple[Any, Any]:
        with self._lock:
            if self._processor is not None and self._model is not None:
                return self._processor, self._model
            if self._load_error:
                raise RuntimeError(self._load_error)
            try:
                from transformers import BlipForConditionalGeneration, BlipProcessor
            except Exception as exc:
                self._load_error = f"BLIP dependencies are unavailable: {exc}"
                raise RuntimeError(self._load_error) from exc

            try:
                processor = BlipProcessor.from_pretrained(self.model_name)
                model = BlipForConditionalGeneration.from_pretrained(self.model_name)
                if self.device:
                    model = model.to(self.device)
                self._processor = processor
                self._model = model
                return processor, model
            except Exception as exc:
                self._load_error = f"failed to load BLIP model {self.model_name}: {exc}"
                raise RuntimeError(self._load_error) from exc

    def _caption_image_local(self, image_path: Path) -> str:
        try:
            from PIL import Image
        except Exception as exc:
            raise RuntimeError(f"Pillow is required for image captioning: {exc}") from exc

        processor, model = self._ensure_local_model()
        with Image.open(image_path) as image:
            rgb_image = image.convert("RGB")
            inputs = processor(images=rgb_image, return_tensors="pt")
        if self.device:
            try:
                inputs = {key: value.to(self.device) for key, value in inputs.items()}
            except Exception:
                logger.debug("Failed to move BLIP inputs to device=%s", self.device, exc_info=True)
        try:
            output = model.generate(**inputs, max_new_tokens=48)
            caption = processor.decode(output[0], skip_special_tokens=True)
        except Exception as exc:
            raise RuntimeError(f"BLIP caption generation failed: {exc}") from exc
        return str(caption or "").strip()

    def _api_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_auth_token:
            token = self.api_auth_token
            if self.api_auth_header.lower() == "authorization" and not token.lower().startswith("bearer "):
                token = f"Bearer {token}"
            headers[self.api_auth_header] = token
        return headers

    def _caption_image_api(self, image_path: Path) -> str:
        if not self.api_url:
            raise RuntimeError("image caption API provider selected but CHAT_IMAGE_CAPTION_API_URL is empty")
        try:
            import requests
        except Exception as exc:
            raise RuntimeError(f"requests is required for API image captioning: {exc}") from exc

        headers = self._api_headers()
        try:
            if self.api_mode == "json_base64":
                mime_type = "application/octet-stream"
                suffix = image_path.suffix.lower()
                if suffix == ".png":
                    mime_type = "image/png"
                elif suffix in {".jpg", ".jpeg"}:
                    mime_type = "image/jpeg"
                elif suffix == ".webp":
                    mime_type = "image/webp"
                elif suffix == ".gif":
                    mime_type = "image/gif"
                encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
                response = requests.post(
                    self.api_url,
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "filename": image_path.name,
                        "mime_type": mime_type,
                        "image_base64": encoded,
                    },
                    timeout=self.api_timeout_seconds,
                )
            else:
                with open(image_path, "rb") as fh:
                    response = requests.post(
                        self.api_url,
                        headers=headers,
                        files={"file": (image_path.name, fh, "application/octet-stream")},
                        timeout=self.api_timeout_seconds,
                    )
        except Exception as exc:
            raise RuntimeError(f"image caption API request failed: {exc}") from exc

        if response.status_code >= 400:
            text = response.text.strip()
            raise RuntimeError(f"image caption API returned {response.status_code}: {text or response.reason}")
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(f"image caption API returned non-JSON response: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("image caption API response must be a JSON object")
        for key in (self.api_caption_field, "blip_caption", "caption", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise RuntimeError(
            f"image caption API response missing caption field; tried {self.api_caption_field}, blip_caption, caption, text"
        )

    def _ensure_openai_client(self) -> Any:
        with self._lock:
            if self._openai_client is not None:
                return self._openai_client
            try:
                import openai
            except Exception as exc:
                raise RuntimeError(f"openai package is required for OpenAI image captioning: {exc}") from exc
            api_key = self.openai_api_key or os.getenv("API_SECRET_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = self.openai_base_url or os.getenv("BASE_URL") or os.getenv("OPENAI_BASE_URL")
            if not str(api_key or "").strip():
                raise RuntimeError("OpenAI image captioning requires API_SECRET_KEY or OPENAI_API_KEY")
            self._openai_client = openai.OpenAI(
                api_key=str(api_key).strip(),
                base_url=str(base_url).strip() if str(base_url or "").strip() else None,
            )
            return self._openai_client

    def _guess_mime_type(self, image_path: Path) -> str:
        suffix = image_path.suffix.lower()
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        if suffix == ".gif":
            return "image/gif"
        return "application/octet-stream"

    def _extract_openai_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        choices = getattr(response, "choices", None)
        if isinstance(choices, list) and choices:
            first = choices[0]
            message = getattr(first, "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str) and content.strip():
                return content.strip()
        raise RuntimeError("OpenAI image caption response did not contain text output")

    def _caption_image_openai(self, image_path: Path) -> str:
        client = self._ensure_openai_client()
        model = self.openai_model or os.getenv("CHAT_IMAGE_CAPTION_OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        mime_type = self._guess_mime_type(image_path)
        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = (
            "Generate one short factual image caption in English for memory storage. "
            "Describe only clearly visible content. No hedging, no markdown, no extra commentary."
        )
        image_url = f"data:{mime_type};base64,{image_data}"
        try:
            response = client.chat.completions.create(
                model=str(model).strip(),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=64,
            )
        except Exception as exc:
            raise RuntimeError(f"OpenAI image caption request failed: {exc}") from exc
        try:
            text = response.choices[0].message.content
        except Exception:
            text = self._extract_openai_text(response)
        if isinstance(text, str) and text.strip():
            return text.strip()
        raise RuntimeError("OpenAI image caption response was empty")

    def caption_image(self, image_path: str | Path) -> str:
        if not self.enabled:
            raise RuntimeError("image captioning is disabled")
        path = Path(image_path).resolve()
        provider = self.provider
        if provider == "openai":
            return self._caption_image_openai(path)
        if provider == "api":
            return self._caption_image_api(path)
        if provider == "local":
            return self._caption_image_local(path)
        raise RuntimeError(f"unsupported image caption provider: {provider}")
