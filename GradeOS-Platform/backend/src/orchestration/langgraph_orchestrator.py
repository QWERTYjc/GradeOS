"""LangGraph orchestrator implementation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from datetime import timezone
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from src.config.runtime_controls import get_runtime_controls
from src.models.run_lifecycle import FailureClass, RunState
from src.orchestration.base import Orchestrator, RunInfo, RunStatus
from src.services.run_observability import RunObservabilityStore
from src.services.run_state_machine import RunStateMachine, classify_failure, map_legacy_status
from src.services.state_snapshot import extract_artifact_refs, sanitize_for_storage, slim_state_for_checkpoint

logger = logging.getLogger(__name__)


class LangGraphOrchestrator(Orchestrator):
    def __init__(self, db_pool: Optional[Any] = None, checkpointer: Optional[Any] = None, offline_mode: bool = False):
        runtime_controls = get_runtime_controls()
        self.db_pool = db_pool if not offline_mode else None
        self.checkpointer = checkpointer or InMemorySaver()
        self._offline_mode = offline_mode

        self._graph_registry: Dict[str, Any] = {}
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self._event_stream_complete: Dict[str, bool] = {}

        self._run_state_machine = RunStateMachine()
        self._observability = RunObservabilityStore(runtime_controls.run_event_buffer_size)
        self._artifact_index: Dict[str, Dict[str, Dict[str, Any]]] = {}

        max_active = runtime_controls.run_max_concurrency
        self._run_semaphore = asyncio.Semaphore(max_active) if max_active > 0 else None
        self._graph_max_concurrency = runtime_controls.run_max_parallel_llm_calls
        self._graph_recursion_limit = int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "50"))
        self._soft_budget_usd = runtime_controls.soft_budget_usd_per_run
        self._budget_warning_emitted: set[str] = set()

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        if isinstance(obj, bytes):
            import base64
            return base64.b64encode(obj).decode("utf-8")
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    def _build_graph_config(self, run_id: str, graph_name: str) -> Dict[str, Any]:
        max_concurrency = self._graph_max_concurrency
        if graph_name == "batch_grading":
            override = os.getenv("GRADING_MAX_WORKERS")
            if override:
                try:
                    max_concurrency = int(override)
                except ValueError:
                    pass
        config: Dict[str, Any] = {"configurable": {"thread_id": run_id}}
        if max_concurrency > 0:
            config["max_concurrency"] = max_concurrency
        if self._graph_recursion_limit > 0:
            config["recursion_limit"] = self._graph_recursion_limit
        return config

    def _track_status(self, run_id: str, status: str, error: Optional[str] = None) -> None:
        state = map_legacy_status(status)
        self._run_state_machine.transition(run_id, state)
        failure_class: Optional[FailureClass] = None
        if status == "failed":
            failure_class = classify_failure(error)
        elif status == "cancelled":
            failure_class = FailureClass.USER_CANCELLED
        self._observability.update_state(run_id, state, status, failure_class=failure_class)

    def _index_artifacts(self, run_id: str, state: Optional[Dict[str, Any]]) -> None:
        if not isinstance(state, dict):
            return
        refs = extract_artifact_refs(run_id, state)
        if not refs:
            return
        self._artifact_index.setdefault(run_id, {}).update(refs)
        for artifact in refs.values():
            self._observability.add_artifact(run_id, artifact)

    def register_graph(self, graph_name: str, compiled_graph: Any):
        self._graph_registry[graph_name] = compiled_graph

    async def start_run(self, graph_name: str, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> str:
        if graph_name not in self._graph_registry:
            raise ValueError(f"Graph not registered: {graph_name}")
        run_id = f"{graph_name}_{idempotency_key}" if idempotency_key else str(uuid.uuid4())
        existing = await self._get_run_from_db(run_id)
        if existing and existing.get("status") in {"pending", "running", "paused"}:
            return run_id
        await self._create_run_in_db(run_id, graph_name, payload)
        task = asyncio.create_task(self._run_graph_background(run_id, graph_name, self._graph_registry[graph_name], payload))
        self._background_tasks[run_id] = task
        return run_id

    async def _run_graph_background(self, run_id: str, graph_name: str, compiled_graph: Any, payload: Dict[str, Any]):
        paused = False
        acquired = False
        try:
            if self._run_semaphore:
                await self._run_semaphore.acquire()
                acquired = True
            await self._update_run_status(run_id, "running")
            config = self._build_graph_config(run_id, graph_name)
            accumulated_state = dict(payload)

            async for event in compiled_graph.astream_events(payload, config=config, version="v2"):
                kind = event.get("event")
                name = event.get("name", "")
                data = event.get("data", {})
                await self._push_event(run_id, {"kind": kind, "name": name, "data": data})

                if kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    content = chunk.content if hasattr(chunk, "content") else (chunk.get("content", "") if isinstance(chunk, dict) else (chunk if isinstance(chunk, str) else ""))
                    if content:
                        await self._push_event(run_id, {"kind": "llm_stream", "name": name, "data": {"chunk": content}})

                if kind == "on_chain_end":
                    output = data.get("output", {})
                    if isinstance(output, dict) and "__interrupt__" in output:
                        paused = True
                        await self._update_run_status(run_id, "paused")
                        await self._push_event(
                            run_id,
                            {
                                "kind": "paused",
                                "name": name or None,
                                "data": {"interrupt_value": output.get("__interrupt__")},
                            },
                        )
                        return
                    if isinstance(output, dict):
                        for key, value in output.items():
                            if key in ("grading_results", "student_results") and isinstance(accumulated_state.get(key), list) and isinstance(value, list):
                                accumulated_state[key].extend(value)
                            else:
                                accumulated_state[key] = value

            # LangGraph v1+ implements pause via `interrupt()` but does NOT emit the interrupt marker
            # inside astream_events outputs. The canonical pause signal is stored in the persisted
            # state snapshot (pending tasks + interrupts). If we detect that, mark the run paused.
            try:
                if hasattr(compiled_graph, "aget_state"):
                    snapshot = await compiled_graph.aget_state(config)
                    tasks = getattr(snapshot, "tasks", None) or ()
                    interrupt_value = None
                    interrupt_node = None
                    for task in tasks:
                        interrupts = getattr(task, "interrupts", None) or ()
                        if interrupts:
                            interrupt_value = getattr(interrupts[0], "value", None)
                            interrupt_node = getattr(task, "name", None)
                            break
                    if interrupt_value is not None:
                        paused = True
                        await self._update_run_status(run_id, "paused")
                        await self._push_event(
                            run_id,
                            {
                                "kind": "paused",
                                "name": interrupt_node,
                                "data": {"interrupt_value": interrupt_value},
                            },
                        )
                        return
            except Exception as exc:
                logger.warning("Failed to detect interrupt state: run_id=%s error=%s", run_id, exc)

            await self._update_run_status(run_id, "completed", output_data=accumulated_state)
            await self._push_event(run_id, {"kind": "completed", "name": None, "data": {"state": accumulated_state}})
        except Exception as exc:
            logger.error("Graph execution failed: run_id=%s error=%s", run_id, exc, exc_info=True)
            await self._update_run_status(run_id, "failed", error=str(exc))
            await self._push_event(run_id, {"kind": "error", "name": None, "data": {"error": str(exc)}})
        finally:
            if acquired and self._run_semaphore:
                self._run_semaphore.release()
            self._background_tasks.pop(run_id, None)
            if not paused:
                await self._mark_event_stream_complete(run_id)

    async def _resume_graph_background(self, run_id: str, graph_name: str, compiled_graph: Any, event_data: Dict[str, Any]):
        paused = False
        acquired = False
        try:
            if self._run_semaphore:
                await self._run_semaphore.acquire()
                acquired = True
            await self._update_run_status(run_id, "running")
            config = self._build_graph_config(run_id, graph_name)
            accumulated_state = await self.get_state(run_id) or {}

            async for event in compiled_graph.astream_events(Command(resume=event_data), config=config, version="v2"):
                kind = event.get("event")
                name = event.get("name", "")
                data = event.get("data", {})
                await self._push_event(run_id, {"kind": kind, "name": name, "data": data})

                if kind == "on_chain_end":
                    output = data.get("output", {})
                    if isinstance(output, dict) and "__interrupt__" in output:
                        paused = True
                        await self._update_run_status(run_id, "paused")
                        await self._push_event(
                            run_id,
                            {
                                "kind": "paused",
                                "name": name or None,
                                "data": {"interrupt_value": output.get("__interrupt__")},
                            },
                        )
                        return
                    if isinstance(output, dict):
                        for key, value in output.items():
                            if key in ("grading_results", "student_results") and isinstance(accumulated_state.get(key), list) and isinstance(value, list):
                                accumulated_state[key].extend(value)
                            else:
                                accumulated_state[key] = value

            # Same pause detection as initial run (see comment above).
            try:
                if hasattr(compiled_graph, "aget_state"):
                    snapshot = await compiled_graph.aget_state(config)
                    tasks = getattr(snapshot, "tasks", None) or ()
                    interrupt_value = None
                    interrupt_node = None
                    for task in tasks:
                        interrupts = getattr(task, "interrupts", None) or ()
                        if interrupts:
                            interrupt_value = getattr(interrupts[0], "value", None)
                            interrupt_node = getattr(task, "name", None)
                            break
                    if interrupt_value is not None:
                        paused = True
                        await self._update_run_status(run_id, "paused")
                        await self._push_event(
                            run_id,
                            {
                                "kind": "paused",
                                "name": interrupt_node,
                                "data": {"interrupt_value": interrupt_value},
                            },
                        )
                        return
            except Exception as exc:
                logger.warning("Failed to detect interrupt state (resume): run_id=%s error=%s", run_id, exc)

            await self._update_run_status(run_id, "completed", output_data=accumulated_state)
            await self._push_event(run_id, {"kind": "completed", "name": None, "data": {"state": accumulated_state}})
        except Exception as exc:
            logger.error("Graph resume failed: run_id=%s error=%s", run_id, exc, exc_info=True)
            await self._update_run_status(run_id, "failed", error=str(exc))
            await self._push_event(run_id, {"kind": "error", "name": None, "data": {"error": str(exc)}})
        finally:
            if acquired and self._run_semaphore:
                self._run_semaphore.release()
            self._background_tasks.pop(run_id, None)
            if not paused:
                await self._mark_event_stream_complete(run_id)

    async def get_status(self, run_id: str) -> RunInfo:
        run = await self._get_run_from_db(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        status_map = {
            "pending": RunStatus.PENDING,
            "running": RunStatus.RUNNING,
            "paused": RunStatus.PAUSED,
            "completed": RunStatus.COMPLETED,
            "failed": RunStatus.FAILED,
            "cancelled": RunStatus.CANCELLED,
            "partial": RunStatus.RUNNING,
        }
        state = await self.get_state(run_id)
        return RunInfo(
            run_id=run_id,
            graph_name=run.get("graph_name", ""),
            status=status_map.get(run.get("status", "pending"), RunStatus.PENDING),
            progress=state.get("progress", {}) if isinstance(state, dict) else {},
            created_at=run.get("created_at", datetime.now()),
            updated_at=run.get("updated_at", datetime.now()),
            error=run.get("error"),
        )

    async def get_run_info(self, run_id: str) -> Optional[RunInfo]:
        run = await self._get_run_from_db(run_id)
        if not run:
            return None
        info = await self.get_status(run_id)
        info.state = await self.get_state(run_id)
        return info

    async def get_state(self, run_id: str) -> Dict[str, Any]:
        try:
            checkpoint = await self.checkpointer.aget({"configurable": {"thread_id": run_id}})
            if checkpoint:
                values = checkpoint.get("channel_values", {})
                if isinstance(values, dict):
                    return values
        except Exception:
            pass
        run = await self._get_run_from_db(run_id)
        if not run:
            return {}
        if isinstance(run.get("output_data"), dict):
            return run["output_data"]
        if isinstance(run.get("input_data"), dict):
            return run["input_data"]
        return {}

    async def get_final_output(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = await self._get_run_from_db(run_id)
        if run and isinstance(run.get("output_data"), dict):
            return run["output_data"]
        return None

    async def cancel(self, run_id: str) -> bool:
        task = self._background_tasks.get(run_id)
        if task and not task.done():
            task.cancel()
        await self._update_run_status(run_id, "cancelled")
        return True

    async def retry(self, run_id: str) -> str:
        run = await self._get_run_from_db(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        payload = run.get("input_data")
        graph_name = run.get("graph_name")
        if not isinstance(payload, dict) or not graph_name:
            raise ValueError("Retry payload unavailable")
        return await self.start_run(graph_name=graph_name, payload=payload)

    async def list_runs(self, graph_name: Optional[str] = None, status: Optional[RunStatus] = None, limit: int = 100, offset: int = 0) -> List[RunInfo]:
        status_map = {
            "pending": RunStatus.PENDING,
            "running": RunStatus.RUNNING,
            "paused": RunStatus.PAUSED,
            "completed": RunStatus.COMPLETED,
            "failed": RunStatus.FAILED,
            "cancelled": RunStatus.CANCELLED,
            "partial": RunStatus.RUNNING,
        }
        runs: List[RunInfo] = []
        for _, run in self._runs.items():
            if graph_name and run.get("graph_name") != graph_name:
                continue
            mapped = status_map.get(run.get("status", "pending"), RunStatus.PENDING)
            if status and mapped != status:
                continue
            runs.append(RunInfo(run_id=run["run_id"], graph_name=run["graph_name"], status=mapped, progress={}, created_at=run["created_at"], updated_at=run["updated_at"], error=run.get("error")))

        if self.db_pool:
            try:
                conditions = []
                params: List[Any] = []
                if graph_name:
                    conditions.append("graph_name = %s")
                    params.append(graph_name)
                if status:
                    conditions.append("status = %s")
                    params.append(status.value)
                where_clause = " AND ".join(conditions) if conditions else "TRUE"
                query = f"SELECT run_id, graph_name, status, created_at, updated_at, error FROM runs WHERE {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                async with self.db_pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(query, params)
                        rows = await cur.fetchall()
                known_ids = {item.run_id for item in runs}
                for run_id, graph_name_value, status_value, created_at, updated_at, error_value in rows:
                    if run_id in known_ids:
                        continue
                    mapped = status_map.get(status_value or "pending", RunStatus.PENDING)
                    runs.append(
                        RunInfo(
                            run_id=run_id,
                            graph_name=graph_name_value,
                            status=mapped,
                            progress={},
                            created_at=created_at or datetime.now(),
                            updated_at=updated_at or datetime.now(),
                            error=error_value,
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to list runs from DB: %s", exc)

        runs.sort(key=lambda item: item.created_at, reverse=True)
        return runs[offset : offset + limit]

    async def recover_incomplete_runs(self, graph_name: Optional[str] = None) -> int:
        resumed = 0
        for run_id, run in list(self._runs.items()):
            status = run.get("status")
            if status not in {"pending", "running"}:
                continue
            graph = run.get("graph_name")
            if not graph or (graph_name and graph != graph_name):
                continue
            if run_id in self._background_tasks:
                continue
            compiled = self._graph_registry.get(graph)
            payload = run.get("input_data")
            if not compiled or not isinstance(payload, dict):
                continue
            task = asyncio.create_task(
                self._run_graph_background(run_id, graph, compiled, payload)
            )
            self._background_tasks[run_id] = task
            resumed += 1
        return resumed

    async def send_event(self, run_id: str, event_type: str, event_data: Dict[str, Any]) -> bool:
        run = await self._get_run_from_db(run_id)
        if not run or run.get("status") != "paused":
            return False
        graph_name = run.get("graph_name")
        compiled = self._graph_registry.get(graph_name)
        if not graph_name or not compiled:
            return False
        task = asyncio.create_task(self._resume_graph_background(run_id, graph_name, compiled, event_data))
        self._background_tasks[run_id] = task
        return True

    async def stream_run(self, run_id: str):
        if run_id not in self._event_queues:
            self._event_queues[run_id] = asyncio.Queue()
        queue = self._event_queues[run_id]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if self._is_event_stream_complete(run_id):
                    break
                continue
            kind = event.get("kind")
            if kind == "__end__":
                break
            if kind == "on_chain_start":
                yield {"type": "node_start", "node": event.get("name"), "data": event.get("data", {})}
            elif kind == "on_chain_end":
                yield {"type": "node_end", "node": event.get("name"), "data": {"output": (event.get("data") or {}).get("output", {})}}
            elif kind in {"llm_stream", "completed", "error", "paused"}:
                yield {"type": kind, "node": event.get("name"), "data": event.get("data", {})}
                if kind in {"completed", "error", "paused"}:
                    break
            elif kind == "budget_warning":
                yield {"type": "budget_warning", "node": None, "data": event.get("data", {})}
            else:
                yield {"type": "event", "node": event.get("name"), "data": event.get("data", {})}
        await self._cleanup_event_queue(run_id)

    async def stream_run_simple(self, run_id: str):
        async for event in self.stream_run(run_id):
            yield event

    async def _push_event(self, run_id: str, event: Dict[str, Any]):
        if run_id not in self._event_queues:
            self._event_queues[run_id] = asyncio.Queue()
        self._observability.push_event(run_id, str(event.get("kind", "unknown")), event.get("name"), event.get("data") or {})

        if self._soft_budget_usd > 0 and run_id not in self._budget_warning_emitted:
            metrics = self._observability.build_metrics(run_id)
            if metrics and metrics.cost.estimated_cost_usd >= self._soft_budget_usd:
                self._budget_warning_emitted.add(run_id)
                warning_event = {
                    "kind": "budget_warning",
                    "name": None,
                    "data": {
                        "run_id": run_id,
                        "estimated_cost_usd": metrics.cost.estimated_cost_usd,
                        "soft_budget_usd": self._soft_budget_usd,
                        "triggered_at": datetime.now(timezone.utc).isoformat(),
                    },
                }
                self._observability.push_event(
                    run_id,
                    "budget_warning",
                    None,
                    warning_event["data"],
                )
                await self._event_queues[run_id].put(warning_event)

        await self._event_queues[run_id].put(event)

    async def _mark_event_stream_complete(self, run_id: str):
        self._event_stream_complete[run_id] = True
        if run_id in self._event_queues:
            await self._event_queues[run_id].put({"kind": "__end__", "name": None, "data": {}})

    def _is_event_stream_complete(self, run_id: str) -> bool:
        return self._event_stream_complete.get(run_id, False)

    async def _cleanup_event_queue(self, run_id: str):
        self._event_queues.pop(run_id, None)
        self._event_stream_complete.pop(run_id, None)
        self._budget_warning_emitted.discard(run_id)

    async def _create_run_in_db(self, run_id: str, graph_name: str, input_data: Dict[str, Any]):
        self._run_state_machine.set_initial(run_id, RunState.CREATED)
        self._observability.register_run(run_id, graph_name, "pending")
        self._runs[run_id] = {
            "run_id": run_id,
            "graph_name": graph_name,
            "status": "pending",
            "input_data": input_data,
            "output_data": None,
            "error": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        if not self.db_pool:
            return
        try:
            storage_input = sanitize_for_storage(input_data)
            async with self.db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO runs (run_id, graph_name, status, input_data, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
                        (run_id, graph_name, "pending", json.dumps(storage_input, default=self._json_serializer), datetime.now(), datetime.now()),
                    )
                await conn.commit()
        except Exception as exc:
            logger.warning("Failed to create run in DB: %s", exc)

    async def _get_run_from_db(self, run_id: str) -> Optional[Dict[str, Any]]:
        if run_id in self._runs:
            return self._runs[run_id]
        if not self.db_pool:
            return None
        try:
            async with self.db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT run_id, graph_name, status, input_data, output_data, error, created_at, updated_at FROM runs WHERE run_id = %s", (run_id,))
                    row = await cur.fetchone()
            if not row:
                return None
            keys = ["run_id", "graph_name", "status", "input_data", "output_data", "error", "created_at", "updated_at"]
            payload = dict(zip(keys, row))
            for field in ("input_data", "output_data"):
                if isinstance(payload.get(field), str):
                    try:
                        payload[field] = json.loads(payload[field])
                    except json.JSONDecodeError:
                        pass
            self._runs[run_id] = payload
            return payload
        except Exception as exc:
            logger.warning("Failed to fetch run from DB: %s", exc)
            return None

    async def _update_run_status(self, run_id: str, status: str, output_data: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        storage_output = None
        if output_data is not None:
            storage_output = slim_state_for_checkpoint(output_data)
            self._index_artifacts(run_id, output_data)
            self._observability.finalize_output(run_id, output_data)

        if run_id in self._runs:
            self._runs[run_id]["status"] = status
            self._runs[run_id]["updated_at"] = datetime.now()
            if storage_output is not None:
                self._runs[run_id]["output_data"] = storage_output
            if error is not None:
                self._runs[run_id]["error"] = error

        if self.db_pool:
            try:
                set_parts = ["status = %s", "updated_at = %s"]
                params: List[Any] = [status, datetime.now()]
                if storage_output is not None:
                    set_parts.append("output_data = %s")
                    params.append(json.dumps(storage_output, default=self._json_serializer))
                if error is not None:
                    set_parts.append("error = %s")
                    params.append(error)
                if status == "completed":
                    set_parts.append("completed_at = %s")
                    params.append(datetime.now())
                params.append(run_id)
                query = f"UPDATE runs SET {', '.join(set_parts)} WHERE run_id = %s"
                async with self.db_pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(query, params)
                    await conn.commit()
            except Exception as exc:
                logger.warning("Failed to update run in DB: %s", exc)

        self._track_status(run_id, status, error)

    async def get_run_metrics(self, run_id: str) -> Optional[Dict[str, Any]]:
        metrics = self._observability.build_metrics(run_id)
        if metrics is None:
            run = await self._get_run_from_db(run_id)
            if not run:
                return None
            self._observability.register_run(run_id, run.get("graph_name", ""), run.get("status", "pending"))
            self._track_status(run_id, run.get("status", "pending"), run.get("error"))
            metrics = self._observability.build_metrics(run_id)
        return metrics.model_dump() if metrics else None

    async def get_run_events(self, run_id: str, after_seq: int = 0, limit: int = 200) -> List[Dict[str, Any]]:
        return self._observability.list_events(run_id, after_seq=after_seq, limit=max(1, limit))

    async def get_run_artifact(self, run_id: str, artifact_id: str) -> Optional[Dict[str, Any]]:
        artifact = self._artifact_index.get(run_id, {}).get(artifact_id)
        if artifact:
            return artifact
        artifact = self._observability.get_artifact(run_id, artifact_id)
        if artifact:
            return artifact
        run = await self._get_run_from_db(run_id)
        if run and isinstance(run.get("output_data"), dict):
            refs = extract_artifact_refs(run_id, run["output_data"])
            self._artifact_index.setdefault(run_id, {}).update(refs)
            return self._artifact_index.get(run_id, {}).get(artifact_id)
        return None
