"""Automatic retention cleanup for grading data.

Policy:
- Keep grading batch data for 7 days by default.
- After expiration, delete the whole batch and all linked records.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from src.utils.database import db

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = int(os.getenv("GRADING_DATA_RETENTION_DAYS", "7"))
DEFAULT_CLEANUP_INTERVAL_SECONDS = int(
    os.getenv("GRADING_DATA_CLEANUP_INTERVAL_SECONDS", "3600")
)
DEFAULT_BATCH_SIZE = int(os.getenv("GRADING_DATA_RETENTION_BATCH_SIZE", "200"))


def _normalize_positive_int(value: int, fallback: int) -> int:
    return value if isinstance(value, int) and value > 0 else fallback


def retention_days() -> int:
    return _normalize_positive_int(DEFAULT_RETENTION_DAYS, 7)


def cleanup_interval_seconds() -> int:
    return _normalize_positive_int(DEFAULT_CLEANUP_INTERVAL_SECONDS, 3600)


def cleanup_batch_size() -> int:
    return _normalize_positive_int(DEFAULT_BATCH_SIZE, 200)


async def _existing_tables(conn: Any, names: Sequence[str]) -> set[str]:
    if not names:
        return set()
    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = ANY(%s)
    """
    result = await conn.execute(query, (list(names),))
    rows = await result.fetchall()
    existing = set()
    for row in rows:
        try:
            existing.add(str(row["table_name"]))
        except Exception:
            existing.add(str(row[0]))
    return existing


async def _fetch_expired_batches(conn: Any, cutoff: datetime, limit: int) -> List[Tuple[str, str]]:
    # Prefer timestamp comparison for modern schema.
    query = """
        SELECT id::text AS history_id, batch_id::text AS batch_id
        FROM grading_history
        WHERE COALESCE(completed_at, created_at)::timestamptz < %s
        ORDER BY COALESCE(completed_at, created_at) ASC
        LIMIT %s
    """
    try:
        result = await conn.execute(query, (cutoff, limit))
        rows = await result.fetchall()
    except Exception:
        # Fallback for legacy text-only schema.
        fallback_query = """
            SELECT id::text AS history_id, batch_id::text AS batch_id
            FROM grading_history
            WHERE COALESCE(completed_at::text, created_at::text) < %s
            ORDER BY created_at ASC
            LIMIT %s
        """
        result = await conn.execute(fallback_query, (cutoff.isoformat(), limit))
        rows = await result.fetchall()

    expired: List[Tuple[str, str]] = []
    for row in rows:
        try:
            history_id = str(row["history_id"])
            batch_id = str(row["batch_id"])
        except Exception:
            history_id = str(row[0])
            batch_id = str(row[1])
        if history_id and batch_id:
            expired.append((history_id, batch_id))
    return expired


async def _delete_with_text_array(
    conn: Any,
    table: str,
    column: str,
    values: Iterable[str],
) -> int:
    payload = [str(v) for v in values if v]
    if not payload:
        return 0
    query = f"DELETE FROM {table} WHERE {column}::text = ANY(%s)"
    result = await conn.execute(query, (payload,))
    return int(getattr(result, "rowcount", 0) or 0)


async def _delete_batch_chunk(
    conn: Any,
    table_names: set[str],
    history_ids: List[str],
    batch_ids: List[str],
) -> Dict[str, int]:
    run_ids = [f"batch_grading_{batch_id}" for batch_id in batch_ids]
    deleted: Dict[str, int] = {}

    if "grading_annotations" in table_names:
        deleted["grading_annotations"] = await _delete_with_text_array(
            conn, "grading_annotations", "grading_history_id", history_ids
        )

    if "grading_page_images" in table_names:
        deleted["grading_page_images"] = await _delete_with_text_array(
            conn, "grading_page_images", "grading_history_id", history_ids
        )

    if "student_grading_results" in table_names:
        deleted["student_grading_results"] = await _delete_with_text_array(
            conn, "student_grading_results", "grading_history_id", history_ids
        )

    if "grading_import_items" in table_names:
        deleted["grading_import_items"] = await _delete_with_text_array(
            conn, "grading_import_items", "batch_id", batch_ids
        )

    if "grading_imports" in table_names:
        deleted["grading_imports"] = await _delete_with_text_array(
            conn, "grading_imports", "batch_id", batch_ids
        )

    if "homework_submissions" in table_names:
        # Keep submission entity, but clear grading outputs for expired batches.
        query = """
            UPDATE homework_submissions
            SET grading_batch_id = NULL, score = NULL, feedback = NULL
            WHERE grading_batch_id::text = ANY(%s)
        """
        result = await conn.execute(query, (batch_ids,))
        deleted["homework_submissions_cleared"] = int(getattr(result, "rowcount", 0) or 0)

    if "batch_images" in table_names:
        deleted["batch_images"] = await _delete_with_text_array(
            conn, "batch_images", "batch_id", batch_ids
        )

    if "workflow_state" in table_names:
        deleted["workflow_state"] = await _delete_with_text_array(
            conn, "workflow_state", "batch_id", batch_ids
        )

    if "stream_events" in table_names and run_ids:
        deleted["stream_events"] = await _delete_with_text_array(
            conn, "stream_events", "stream_id", run_ids
        )

    if "enhanced_checkpoint_writes" in table_names and run_ids:
        deleted["enhanced_checkpoint_writes"] = await _delete_with_text_array(
            conn, "enhanced_checkpoint_writes", "thread_id", run_ids
        )

    if "enhanced_checkpoints" in table_names and run_ids:
        deleted["enhanced_checkpoints"] = await _delete_with_text_array(
            conn, "enhanced_checkpoints", "thread_id", run_ids
        )

    if "runs" in table_names and run_ids:
        deleted["runs"] = await _delete_with_text_array(conn, "runs", "run_id", run_ids)
    if "attempts" in table_names and run_ids:
        deleted["attempts"] = await _delete_with_text_array(conn, "attempts", "run_id", run_ids)

    if "grading_history" in table_names:
        query = """
            DELETE FROM grading_history
            WHERE id::text = ANY(%s) OR batch_id::text = ANY(%s)
        """
        result = await conn.execute(query, (history_ids, batch_ids))
        deleted["grading_history"] = int(getattr(result, "rowcount", 0) or 0)

    return deleted


async def run_grading_retention_cleanup_once(
    *,
    keep_days: int | None = None,
    batch_limit: int | None = None,
) -> Dict[str, Any]:
    """Delete expired grading batches and linked records once."""
    if not db.is_available:
        return {"status": "skipped", "reason": "database_unavailable"}

    keep_days = _normalize_positive_int(keep_days or retention_days(), 7)
    batch_limit = _normalize_positive_int(batch_limit or cleanup_batch_size(), 200)
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)

    totals: Dict[str, int] = {"expired_batches": 0}
    max_rounds = 100

    for _ in range(max_rounds):
        async with db.connection() as conn:
            table_names = await _existing_tables(
                conn,
                [
                    "grading_history",
                    "student_grading_results",
                    "grading_page_images",
                    "grading_annotations",
                    "grading_imports",
                    "grading_import_items",
                    "batch_images",
                    "workflow_state",
                    "runs",
                    "attempts",
                    "stream_events",
                    "enhanced_checkpoints",
                    "enhanced_checkpoint_writes",
                    "homework_submissions",
                ],
            )

            if "grading_history" not in table_names:
                return {"status": "skipped", "reason": "grading_history_not_found"}

            expired = await _fetch_expired_batches(conn, cutoff, batch_limit)
            if not expired:
                break

            history_ids = [item[0] for item in expired]
            batch_ids = [item[1] for item in expired]
            chunk_deleted = await _delete_batch_chunk(conn, table_names, history_ids, batch_ids)
            await conn.commit()

            totals["expired_batches"] += len(batch_ids)
            for key, value in chunk_deleted.items():
                totals[key] = totals.get(key, 0) + int(value or 0)

            # Safety: stop if parent rows were not removed to avoid endless loops.
            if chunk_deleted.get("grading_history", 0) == 0:
                logger.warning(
                    "[Retention] No grading_history rows deleted for expired chunk; stopping early."
                )
                break

    totals.update(
        {
            "status": "ok",
            "retention_days": keep_days,
            "cutoff": cutoff.isoformat(),
        }
    )
    return totals


async def grading_retention_worker_loop(
    *,
    interval_seconds: int | None = None,
    run_immediately: bool = True,
) -> None:
    """Background worker for periodic grading-retention cleanup."""
    interval = _normalize_positive_int(interval_seconds or cleanup_interval_seconds(), 3600)

    if run_immediately:
        try:
            summary = await run_grading_retention_cleanup_once()
            logger.info("[Retention] startup cleanup summary: %s", summary)
        except Exception as exc:
            logger.warning("[Retention] startup cleanup failed: %s", exc)

    while True:
        try:
            await asyncio.sleep(interval)
            summary = await run_grading_retention_cleanup_once()
            logger.info("[Retention] periodic cleanup summary: %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[Retention] periodic cleanup failed: %s", exc)
