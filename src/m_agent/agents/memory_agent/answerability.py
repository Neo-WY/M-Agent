"""Workspace answerability evaluation.

Provides both a fast rule-based pre-filter and an LLM-based deep judge.

The LLM judge returns a structured decision containing:
- ``status``: ``SUFFICIENT`` / ``INSUFFICIENT`` / ``INVALID``
- ``useful_evidence_ids``: which evidence the judge considers genuinely useful
- ``reason``: human-readable explanation
- ``next_query``: when ``INSUFFICIENT``, the query for the next retrieval round
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, TypedDict

from .workspace import Workspace, WorkspaceDocument, WorkspaceStatus

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")
_EVIDENCE_REF_PREFIX_RE = re.compile(r"^\s*ref\s*[:：]\s*", flags=re.IGNORECASE)
_JUDGE_RAW_LOG_MAX_CHARS = 12000


class _JudgeDecisionRequired(TypedDict):
    status: WorkspaceStatus
    useful_evidence_ids: List[str]
    reason: str
    next_query: str | None
    gap_type: str | None


class JudgeDecision(_JudgeDecisionRequired, total=False):
    parse_failed: bool


# ---------------------------------------------------------------------------
# Direct judge (no evidence binding)
# ---------------------------------------------------------------------------

class _DirectJudgeDecisionRequired(TypedDict):
    useful_information: str
    answer: str | None
    next_query: str | None


class DirectJudgeDecision(_DirectJudgeDecisionRequired, total=False):
    parse_failed: bool


def llm_judge_direct(
    *,
    llm_func: Callable[[str], Any],
    prompt_text: str,
) -> DirectJudgeDecision:
    """Judge-driven decision without workspace status/evidence binding.

    Expected JSON schema:
    {
      "useful_information": "...",
      "answer": "..." | null,
      "next_query": "..." | null
    }

    Constraint: exactly one of answer / next_query should be non-empty.
    """
    raw_response = llm_func(prompt_text)
    response_text = _extract_text(raw_response)
    parsed = _parse_judge_response(response_text)
    parse_failed = not bool(parsed)
    if parse_failed:
        logger.warning(
            "direct_judge parse_failed=true; raw_response follows (truncated=%s chars)\n"
            "=== direct_judge_raw_response_begin ===\n%s\n"
            "=== direct_judge_raw_response_end ===",
            _JUDGE_RAW_LOG_MAX_CHARS,
            _clip_for_log(response_text, _JUDGE_RAW_LOG_MAX_CHARS),
        )

    useful_information = str(parsed.get("useful_information", "") or "").strip()

    answer_raw = parsed.get("answer")
    answer = str(answer_raw).strip() if isinstance(answer_raw, str) else None
    if isinstance(answer, str) and not answer:
        answer = None

    next_query_raw = parsed.get("next_query")
    next_query = str(next_query_raw).strip() if isinstance(next_query_raw, str) else None
    if isinstance(next_query, str) and not next_query:
        next_query = None

    # Enforce mutual exclusion with a conservative fail-safe.
    if answer and next_query:
        # Prefer answer (stop condition) and discard next_query.
        next_query = None
    elif not answer and not next_query:
        # If both missing, mark parse_failed so caller can preserve existing cur_query.
        parse_failed = True

    return {
        "useful_information": useful_information,
        "answer": answer,
        "next_query": next_query,
        "parse_failed": parse_failed,
    }


# ---------------------------------------------------------------------------
# Fast rule-based pre-filter (zero LLM calls)
# ---------------------------------------------------------------------------

def quick_reject(workspace: Workspace, new_evidence_ids: List[str]) -> Optional[JudgeDecision]:
    """Return a decision immediately if the workspace is obviously empty.

    Returns ``None`` when the quick check cannot decide and LLM judge is needed.
    """
    kept = workspace.kept_evidences()
    if not kept:
        return {
            "status": "INVALID",
            "useful_evidence_ids": [],
            "reason": "Workspace has no kept evidence at all.",
            "next_query": None,
            "gap_type": "no_evidence",
        }

    has_any = any(_has_any_useful_content(ev) for ev in kept)
    if not has_any:
        return {
            "status": "INVALID",
            "useful_evidence_ids": [],
            "reason": "All kept evidence lack both turn content and facts.",
            "next_query": None,
            "gap_type": "empty_evidence",
        }

    return None


# ---------------------------------------------------------------------------
# LLM judge
# ---------------------------------------------------------------------------

def llm_judge_workspace(
    workspace: Workspace,
    new_evidence_ids: List[str],
    *,
    ref_id_to_evidence_id: Dict[str, str] | None = None,
    llm_func: Callable[[str], Any],
    prompt_text: str,
) -> JudgeDecision:
    """Call the LLM to evaluate workspace evidence sufficiency.

    ``prompt_text`` should already have all placeholders rendered.
    ``llm_func`` is the model invocation callable (same as used elsewhere).
    """
    quick = quick_reject(workspace, new_evidence_ids)
    if quick is not None:
        return quick

    raw_response = llm_func(prompt_text)
    response_text = _extract_text(raw_response)
    parsed = _parse_judge_response(response_text)
    parse_failed = not bool(parsed)
    if parse_failed:
        logger.warning(
            "workspace_judge parse_failed=true; raw_response follows (truncated=%s chars)\n"
            "=== workspace_judge_raw_response_begin ===\n%s\n"
            "=== workspace_judge_raw_response_end ===",
            _JUDGE_RAW_LOG_MAX_CHARS,
            _clip_for_log(response_text, _JUDGE_RAW_LOG_MAX_CHARS),
        )

    status = parsed.get("status", "").strip().upper()
    if status not in {"SUFFICIENT", "INSUFFICIENT", "INVALID"}:
        logger.warning("LLM judge returned unexpected status '%s', defaulting to INSUFFICIENT", status)
        status = "INSUFFICIENT"

    useful_ids = parsed.get("useful_evidence_ids", [])
    if not isinstance(useful_ids, list):
        useful_ids = []
    useful_ids = [_normalize_evidence_id(eid) for eid in useful_ids]
    useful_ids = [eid for eid in useful_ids if eid]
    if ref_id_to_evidence_id:
        # The judge may return short ref ids (e.g. E1/E2). Map them back to workspace evidence_id.
        mapped: List[str] = []
        for rid in useful_ids:
            eid = ref_id_to_evidence_id.get(rid)
            if eid:
                mapped.append(eid)
        useful_ids = mapped

    reason = str(parsed.get("reason", "") or "").strip() or "LLM judge decision."
    next_query = parsed.get("next_query")
    if isinstance(next_query, str):
        next_query = next_query.strip() or None
    else:
        next_query = None

    if status == "INVALID":
        new_set = set(new_evidence_ids)
        any_new_useful = any(eid in new_set for eid in useful_ids)
        if any_new_useful:
            status = "INSUFFICIENT"
            logger.info("LLM said INVALID but selected new evidence as useful; upgrading to INSUFFICIENT")

    gap_type: str | None = None
    if status == "INSUFFICIENT":
        gap_type = "need_more_evidence"
    elif status == "INVALID":
        gap_type = "round_produced_nothing"

    return {
        "status": status,  # type: ignore[typeddict-item]
        "useful_evidence_ids": useful_ids,
        "reason": reason,
        "next_query": next_query,
        "gap_type": gap_type,
        "parse_failed": parse_failed,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if hasattr(response, "content"):
        return str(response.content)
    return str(response)


def _parse_judge_response(text: str) -> Dict[str, Any]:
    match = _JSON_BLOCK_RE.search(text or "")
    if not match:
        logger.warning("Could not extract JSON from judge response")
        return {}
    raw = match.group()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse judge JSON: %s", exc)
        repaired = _repair_common_judge_json_issues(raw)
        if repaired != raw:
            try:
                parsed = json.loads(repaired)
                logger.warning(
                    "workspace_judge JSON parse succeeded after auto-repair of common escape issues"
                )
                return parsed
            except json.JSONDecodeError as exc2:
                logger.warning("Judge JSON still invalid after auto-repair: %s", exc2)
        return {}


def _has_any_useful_content(doc: WorkspaceDocument) -> bool:
    return bool(str(doc.get("content", "") or "").strip())


def _normalize_evidence_id(raw: Any) -> str:
    """Normalize evidence ids returned by the LLM judge.

    The workspace prompt labels evidences as ``ref: <evidence_id>``. Some models
    copy the ``ref:`` prefix back into ``useful_evidence_ids``; downstream
    workspace pruning expects the bare ``evidence_id``.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    text = _EVIDENCE_REF_PREFIX_RE.sub("", text).strip()
    # Defensive stripping for common wrappers the judge might emit.
    if (text.startswith("`") and text.endswith("`")) or (text.startswith('"') and text.endswith('"')):
        text = text[1:-1].strip()
    return text


def _clip_for_log(text: str, max_chars: int) -> str:
    body = str(text or "")
    if len(body) <= max_chars:
        return body
    return body[:max_chars] + "\n...(truncated)..."


def _repair_common_judge_json_issues(text: str) -> str:
    """Best-effort repair for common LLM JSON quoting mistakes.

    Current target: values incorrectly written as \\\"...\\\" after a colon.
    Example bad:  "next_query": \"foo\"
    Example good: "next_query": "foo"
    """
    fixed = str(text or "")
    # Fix opening escaped quote after ":".
    fixed = re.sub(r'(:\s*)\\"', r'\1"', fixed)
    # Fix closing escaped quote before comma/object end.
    fixed = re.sub(r'\\"(\s*[,}\]])', r'"\1', fixed)
    return fixed
