from __future__ import annotations

import json
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .chat_image_captioner import ChatImageCaptioner

_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_segment(value: Optional[str], *, fallback: str) -> str:
    raw = str(value or "").strip()
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in raw).strip("_")
    return cleaned or fallback


class ChatImageStore:
    def __init__(
        self,
        *,
        root_dir: Path,
        captioner: Optional[ChatImageCaptioner] = None,
        max_size_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.captioner = captioner or ChatImageCaptioner()
        self.max_size_bytes = max(1, int(max_size_bytes))
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _user_upload_dir(self, *, username: Optional[str], month_key: str) -> Path:
        user_key = _safe_segment(username, fallback="anonymous")
        user_dir = self.root_dir / f"user_{user_key}"
        return user_dir / "uploads" / "images" / month_key

    def save_upload(
        self,
        *,
        content: bytes,
        content_type: str,
        original_filename: str,
        username: Optional[str],
        thread_id: Optional[str],
    ) -> Dict[str, Any]:
        safe_content_type = str(content_type or "").strip().lower()
        if safe_content_type not in _ALLOWED_IMAGE_TYPES:
            guessed, _ = mimetypes.guess_type(str(original_filename or ""))
            safe_content_type = str(guessed or safe_content_type or "").strip().lower()
        extension = _ALLOWED_IMAGE_TYPES.get(safe_content_type)
        if extension is None:
            raise ValueError("unsupported image content type")

        payload = bytes(content or b"")
        if not payload:
            raise ValueError("image file is empty")
        if len(payload) > self.max_size_bytes:
            raise ValueError(f"image exceeds max size of {self.max_size_bytes} bytes")

        upload_id = f"img_{uuid.uuid4().hex}"
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        save_dir = self._user_upload_dir(username=username, month_key=month_key)
        save_dir.mkdir(parents=True, exist_ok=True)

        image_path = save_dir / f"{upload_id}{extension}"
        meta_path = save_dir / f"{upload_id}.json"
        image_path.write_bytes(payload)

        try:
            width = None
            height = None
            try:
                from PIL import Image

                with Image.open(image_path) as image:
                    width, height = image.size
            except Exception:
                width = None
                height = None

            blip_caption = self.captioner.caption_image(image_path)
            image_url = f"/v1/chat/uploads/images/{upload_id}/content"
            image_file = str(image_path)
            metadata = {
                "upload_id": upload_id,
                "owner": str(username or "").strip() or None,
                "thread_id": str(thread_id or "").strip() or None,
                "original_filename": str(original_filename or "").strip() or None,
                "mime_type": safe_content_type,
                "size_bytes": len(payload),
                "width": width,
                "height": height,
                "image_file": image_file,
                "image_url": image_url,
                "blip_caption": blip_caption,
                "created_at": _now_iso(),
            }
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return metadata
        except Exception:
            try:
                if image_path.exists():
                    image_path.unlink()
                if meta_path.exists():
                    meta_path.unlink()
            except Exception:
                pass
            raise

    def get_upload_metadata(self, upload_id: str) -> Optional[Dict[str, Any]]:
        safe_upload_id = str(upload_id or "").strip()
        if not safe_upload_id:
            return None
        for meta_path in self.root_dir.rglob(f"{safe_upload_id}.json"):
            try:
                payload = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload
        return None
