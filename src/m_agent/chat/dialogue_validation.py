"""Validate on-disk / uploaded chat dialogue JSON before import."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAX_DIALOGUE_FILE_BYTES = 5 * 1024 * 1024
MAX_TURNS_PER_DIALOGUE = 500
MAX_TURNS_PER_TURN = MAX_TURNS_PER_DIALOGUE  # backwards-compat alias in checks
MAX_TEXT_LEN_PER_TURN = 32_000
_DIALOGUE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _err(code: str, message: str, *, field: str = "") -> Dict[str, str]:
    item: Dict[str, str] = {"code": code, "message": message}
    if field:
        item["field"] = field
    return item


def safe_upload_basename(filename: str) -> str:
    """Strip path components from client-provided names."""
    name = Path(str(filename or "").replace("\\", "/")).name
    if not name or name in {".", ".."}:
        return "upload.json"
    return name[:200]


def parse_dialogue_json_bytes(
    data: bytes,
    *,
    filename: str = "upload.json",
    max_bytes: int = MAX_DIALOGUE_FILE_BYTES,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, str]]]:
    errors: List[Dict[str, str]] = []
    if not isinstance(data, (bytes, bytearray)):
        return None, [_err("invalid_payload", "file body must be bytes")]
    if len(data) > max_bytes:
        return None, [_err("file_too_large", f"file exceeds {max_bytes} bytes", field="file")]
    if not data.strip():
        return None, [_err("empty_file", "file is empty", field="file")]

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, [_err("invalid_encoding", "file must be UTF-8 JSON", field="file")]

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [_err("invalid_json", f"JSON parse error: {exc}", field="file")]

    if not isinstance(payload, dict):
        return None, [_err("invalid_root", "dialogue document must be a JSON object", field="file")]

    ok, _, val_errors = validate_dialogue_payload(payload, source_name=safe_upload_basename(filename))
    if not ok:
        return None, val_errors
    return payload, []


def validate_dialogue_payload(
    payload: Dict[str, Any],
    *,
    source_name: str = "",
) -> Tuple[bool, Dict[str, Any], List[Dict[str, str]]]:
    """Return (ok, summary, errors). Summary includes dialogue_id, thread_id, round_count."""
    errors: List[Dict[str, str]] = []
    if not isinstance(payload, dict):
        return False, {}, [_err("invalid_root", "dialogue document must be a JSON object")]

    dialogue_id = str(payload.get("dialogue_id", "") or "").strip()
    if not dialogue_id:
        stem = Path(safe_upload_basename(source_name)).stem
        dialogue_id = stem if stem and stem != "upload" else ""
    if not dialogue_id:
        errors.append(_err("missing_dialogue_id", "dialogue_id is required (or use a descriptive .json filename)"))
    elif not _DIALOGUE_ID_RE.match(dialogue_id):
        errors.append(
            _err(
                "invalid_dialogue_id",
                "dialogue_id must be 1-128 chars: letters, digits, underscore, dot, hyphen",
                field="dialogue_id",
            )
        )

    meta = payload.get("meta")
    if meta is not None and not isinstance(meta, dict):
        errors.append(_err("invalid_meta", "meta must be an object when present", field="meta"))
        meta = {}
    elif not isinstance(meta, dict):
        meta = {}

    thread_id = str(meta.get("thread_id", "") or "").strip()
    if thread_id and len(thread_id) > 256:
        errors.append(_err("invalid_thread_id", "meta.thread_id is too long", field="meta.thread_id"))

    turns = payload.get("turns")
    if not isinstance(turns, list):
        errors.append(_err("invalid_turns", "turns must be a non-empty array", field="turns"))
        turns = []
    elif not turns:
        errors.append(_err("empty_turns", "turns must contain at least one message", field="turns"))
    elif len(turns) > MAX_TURNS_PER_TURN:
        errors.append(
            _err(
                "too_many_turns",
                f"turns exceeds maximum of {MAX_TURNS_PER_TURN}",
                field="turns",
            )
        )

    valid_turn_count = 0
    for idx, turn in enumerate(turns if isinstance(turns, list) else []):
        if not isinstance(turn, dict):
            errors.append(_err("invalid_turn", f"turns[{idx}] must be an object", field=f"turns[{idx}]"))
            continue
        speaker = str(turn.get("speaker", "") or "").strip()
        text = str(turn.get("text", "") or "").strip()
        if not speaker:
            errors.append(_err("missing_speaker", f"turns[{idx}].speaker is required", field=f"turns[{idx}].speaker"))
        if not text:
            errors.append(_err("missing_text", f"turns[{idx}].text is required", field=f"turns[{idx}].text"))
        elif len(text) > MAX_TEXT_LEN_PER_TURN:
            errors.append(
                _err(
                    "text_too_long",
                    f"turns[{idx}].text exceeds {MAX_TEXT_LEN_PER_TURN} characters",
                    field=f"turns[{idx}].text",
                )
            )
        if speaker and text and len(text) <= MAX_TEXT_LEN_PER_TURN:
            valid_turn_count += 1

    user_name = str(payload.get("user_id", "") or "").strip()
    participants = payload.get("participants")
    assistant_name = "Memory Assistant"
    if isinstance(participants, list) and len(participants) >= 2:
        user_name = str(participants[0] or user_name).strip() or user_name
        assistant_name = str(participants[1] or assistant_name).strip() or assistant_name

    from m_agent.chat.dialogue_import import turns_to_rounds

    rounds = turns_to_rounds(
        turns if isinstance(turns, list) else [],
        user_speaker=user_name or "User",
        assistant_speaker=assistant_name,
    )
    if valid_turn_count > 0 and not rounds:
        errors.append(
            _err(
                "unpairable_turns",
                "turns must include at least one user/assistant pair for memory indexing",
                field="turns",
            )
        )

    summary = {
        "dialogue_id": dialogue_id,
        "thread_id": thread_id or "imported-thread",
        "round_count": len(rounds),
        "turn_count": valid_turn_count,
        "source_name": source_name,
    }
    return len(errors) == 0, summary, errors


__all__ = [
    "MAX_DIALOGUE_FILE_BYTES",
    "parse_dialogue_json_bytes",
    "safe_upload_basename",
    "validate_dialogue_payload",
]
