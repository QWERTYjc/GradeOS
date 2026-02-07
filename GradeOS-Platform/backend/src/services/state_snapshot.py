"""Helpers for state slimming, storage-safe serialization, and artifact indexing."""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.models.run_lifecycle import ArtifactRef


HEAVY_STATE_KEYS = {"answer_images", "processed_images", "rubric_images"}
MAX_INLINE_STRING_LENGTH = 4096


def _safe_sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _bytes_summary(value: bytes) -> Dict[str, Any]:
    return {
        "_kind": "bytes_ref",
        "size": len(value),
        "sha1": _safe_sha1(value),
    }


def _string_summary(value: str) -> Dict[str, Any]:
    raw = value.encode("utf-8", errors="ignore")
    return {
        "_kind": "text_ref",
        "size": len(raw),
        "sha1": _safe_sha1(raw),
    }


def sanitize_for_storage(payload: Any, key_hint: Optional[str] = None) -> Any:
    """Convert payload to JSON-serializable form and trim heavy fields."""
    if payload is None:
        return None
    if isinstance(payload, (int, float, bool)):
        return payload
    if isinstance(payload, bytes):
        return _bytes_summary(payload)
    if isinstance(payload, bytearray):
        return _bytes_summary(bytes(payload))
    if isinstance(payload, str):
        if len(payload) > MAX_INLINE_STRING_LENGTH:
            return _string_summary(payload)
        return payload

    if isinstance(payload, list):
        if key_hint in HEAVY_STATE_KEYS:
            first_item = payload[0] if payload else None
            first_type = type(first_item).__name__ if first_item is not None else "unknown"
            return {
                "_kind": "list_ref",
                "key": key_hint,
                "count": len(payload),
                "item_type": first_type,
            }
        return [sanitize_for_storage(item) for item in payload]

    if isinstance(payload, dict):
        result: Dict[str, Any] = {}
        for key, value in payload.items():
            result[str(key)] = sanitize_for_storage(value, key_hint=str(key))
        return result

    # Fallback for complex objects.
    return str(payload)


def slim_state_for_checkpoint(state: Dict[str, Any]) -> Dict[str, Any]:
    """Remove or summarize large fields before storing run output."""
    if not isinstance(state, dict):
        return {}
    return sanitize_for_storage(state)


def extract_artifact_refs(
    run_id: str,
    state: Optional[Dict[str, Any]],
    *,
    public_download_prefix: str = "/api/batch/files",
) -> Dict[str, Dict[str, Any]]:
    """Build artifact reference index from state payload."""
    if not isinstance(state, dict):
        return {}

    refs: Dict[str, Dict[str, Any]] = {}

    file_index = state.get("file_index_by_page")
    if isinstance(file_index, dict):
        for raw_page, item in file_index.items():
            if not isinstance(item, dict):
                continue
            file_id = item.get("file_id")
            if not file_id:
                continue
            artifact_id = f"page_{raw_page}"
            uri = f"{public_download_prefix}/{file_id}/download"
            refs[artifact_id] = ArtifactRef(
                artifact_id=artifact_id,
                uri=uri,
                hash=item.get("hash"),
                metadata={
                    "run_id": run_id,
                    "source": "file_index_by_page",
                    "page_index": raw_page,
                    "content_type": item.get("content_type"),
                    "file_id": file_id,
                },
            ).model_dump()

    # Keep lightweight references for known heavy keys.
    for key in HEAVY_STATE_KEYS:
        value = state.get(key)
        if isinstance(value, list):
            artifact_id = f"{key}_ref"
            refs[artifact_id] = ArtifactRef(
                artifact_id=artifact_id,
                uri=f"memory://{run_id}/{key}",
                hash=None,
                metadata={
                    "run_id": run_id,
                    "source": "state",
                    "field": key,
                    "count": len(value),
                },
            ).model_dump()

    return refs


def build_stable_cache_key(
    rubric_hash: str,
    answer_hash: str,
    prompt_version: str,
    model: str,
) -> str:
    """Canonical cache key format required by the plan."""
    return f"{rubric_hash}:{answer_hash}:{prompt_version}:{model}"


def try_decode_base64_blob(blob: str) -> Tuple[bool, Optional[bytes]]:
    """Best-effort base64 decoder used by artifact helpers."""
    try:
        return True, base64.b64decode(blob, validate=True)
    except Exception:
        return False, None
