"""
Per-call LLM telemetry: latency, tokens, model, engine, success/failure.

Records are buffered in-memory and flushed to MongoDB llm_calls collection
in background batches to avoid blocking the request path.
"""

import asyncio
import logging
import time
import threading
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger("llm_telemetry")


class LLMTelemetry:
    """
    In-memory telemetry aggregator with async MongoDB persistence.

    Usage:
        record = telemetry.start("explainer", "Mistral-Large")
        ... do LLM call ...
        telemetry.finish(record, ok=True, tokens_in=150, tokens_out=300)
    """

    def __init__(self, db_collection=None, flush_interval: float = 10.0, buffer_size: int = 100):
        self._buffer: deque = deque(maxlen=5000)
        self._lock = threading.Lock()
        self._db_collection = db_collection
        self._flush_interval = flush_interval
        self._buffer_size = buffer_size
        self._flush_task: Optional[asyncio.Task] = None

        # In-memory rolling stats (last N calls per model)
        self._stats_window = 1000
        self._per_model: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self._stats_window))

    # ----------------------------------
    # RECORD LIFECYCLE
    # ----------------------------------

    def start(self, engine: str, model_name: str, prompt_version: str = "v1") -> Dict:
        """Create a telemetry record. Call finish() when the LLM call completes."""
        return {
            "engine": engine,
            "model": model_name,
            "prompt_version": prompt_version,
            "start_ts": time.time(),
            "latency_ms": None,
            "tokens_in": None,
            "tokens_out": None,
            "ok": False,
            "error": None,
        }

    def finish(
        self,
        record: Dict,
        ok: bool = True,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """Complete a telemetry record and buffer it."""
        record["latency_ms"] = round((time.time() - record["start_ts"]) * 1000, 1)
        record["ok"] = ok
        record["tokens_in"] = tokens_in
        record["tokens_out"] = tokens_out
        record["error"] = error

        with self._lock:
            self._buffer.append(record)
            self._per_model[record["model"]].append(record)

        logger.debug(
            "llm_call engine=%s model=%s latency=%.1fms ok=%s tokens_in=%s tokens_out=%s",
            record["engine"], record["model"], record["latency_ms"],
            ok, tokens_in, tokens_out,
        )

    # ----------------------------------
    # IN-MEMORY STATS
    # ----------------------------------

    def summary(self, window_hours: float = 24.0) -> Dict:
        """
        Return per-model summary: call count, avg latency, failure rate.
        Filters to calls within window_hours.
        """
        cutoff = time.time() - (window_hours * 3600)
        result = {}

        with self._lock:
            for model_name, records in self._per_model.items():
                recent = [r for r in records if r["start_ts"] >= cutoff]
                if not recent:
                    continue

                total = len(recent)
                failures = sum(1 for r in recent if not r["ok"])
                latencies = [r["latency_ms"] for r in recent if r["latency_ms"] is not None]
                tokens_in_total = sum(r["tokens_in"] or 0 for r in recent)
                tokens_out_total = sum(r["tokens_out"] or 0 for r in recent)

                result[model_name] = {
                    "calls": total,
                    "failures": failures,
                    "failure_rate": round(failures / max(1, total), 3),
                    "avg_latency_ms": round(sum(latencies) / max(1, len(latencies)), 1),
                    "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 1),
                    "total_tokens_in": tokens_in_total,
                    "total_tokens_out": tokens_out_total,
                }

        # Per-engine breakdown
        engine_stats = defaultdict(lambda: {"calls": 0, "failures": 0})
        with self._lock:
            for records in self._per_model.values():
                for r in records:
                    if r["start_ts"] >= cutoff:
                        engine_stats[r["engine"]]["calls"] += 1
                        if not r["ok"]:
                            engine_stats[r["engine"]]["failures"] += 1

        return {
            "window_hours": window_hours,
            "per_model": result,
            "per_engine": dict(engine_stats),
        }

    def cost_summary(self, window_hours: float = 24.0) -> Dict:
        """
        Return estimated cost breakdown by model and tier (P3.3).
        Uses MODEL_COST_PER_1K from llm_registry for per-token cost estimation.
        """
        from core.llm_registry import MODEL_COST_PER_1K, get_tier_for_engine

        cutoff = time.time() - (window_hours * 3600)
        per_model_cost = {}
        per_tier = {"cheap": {"calls": 0, "tokens": 0, "est_cost": 0.0},
                    "strong": {"calls": 0, "tokens": 0, "est_cost": 0.0}}
        total_cost = 0.0

        with self._lock:
            for model_name, records in self._per_model.items():
                recent = [r for r in records if r["start_ts"] >= cutoff and r["ok"]]
                if not recent:
                    continue

                # Strip the per-key "#<idx>" suffix (e.g. "Mistral-Large#2") so
                # the cost table (keyed by base label) still matches.
                _base_label = model_name.split("#")[0]
                cost_per_1k = MODEL_COST_PER_1K.get(_base_label, 0.001)
                tokens_in = sum(r["tokens_in"] or 0 for r in recent)
                tokens_out = sum(r["tokens_out"] or 0 for r in recent)
                total_tokens = tokens_in + tokens_out
                est_cost = (total_tokens / 1000) * cost_per_1k

                per_model_cost[model_name] = {
                    "calls": len(recent),
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_per_1k": cost_per_1k,
                    "est_cost_usd": round(est_cost, 6),
                }
                total_cost += est_cost

                # Aggregate by tier using engine from each record
                for r in recent:
                    tier = get_tier_for_engine(r.get("engine", ""))
                    per_tier[tier]["calls"] += 1
                    per_tier[tier]["tokens"] += (r["tokens_in"] or 0) + (r["tokens_out"] or 0)

            # Calculate tier costs
            for tier_name, tier_data in per_tier.items():
                if tier_data["tokens"] > 0:
                    # Use average cost rate for that tier
                    avg_rate = 0.00010 if tier_name == "cheap" else 0.00200
                    tier_data["est_cost"] = round(
                        (tier_data["tokens"] / 1000) * avg_rate, 6
                    )

        return {
            "window_hours": window_hours,
            "per_model": per_model_cost,
            "per_tier": per_tier,
            "total_est_cost_usd": round(total_cost, 6),
        }

    # ----------------------------------
    # MONGODB PERSISTENCE (BACKGROUND)
    # ----------------------------------

    async def start_flush_loop(self):
        """Start background task that periodically flushes buffer to MongoDB."""
        if self._db_collection is None:
            return
        if self._flush_task is not None:
            return
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self):
        """Periodically flush buffered records to MongoDB."""
        while True:
            await asyncio.sleep(self._flush_interval)
            await self._flush_to_db()

    async def _flush_to_db(self):
        """Write buffered records to MongoDB."""
        if self._db_collection is None:
            return

        batch: List[Dict] = []
        with self._lock:
            while self._buffer and len(batch) < self._buffer_size:
                batch.append(self._buffer.popleft())

        if not batch:
            return

        try:
            await self._db_collection.insert_many(batch, ordered=False)
            logger.debug("Flushed %d telemetry records to MongoDB", len(batch))
        except Exception as e:
            logger.warning("Failed to flush telemetry: %s", e)
            # Put records back
            with self._lock:
                for r in reversed(batch):
                    self._buffer.appendleft(r)


# ----------------------------------
# SINGLETON
# ----------------------------------

_telemetry_instance: Optional[LLMTelemetry] = None
_telemetry_lock = threading.Lock()


def get_telemetry() -> LLMTelemetry:
    """Return the shared telemetry instance (singleton)."""
    global _telemetry_instance
    if _telemetry_instance is not None:
        return _telemetry_instance

    with _telemetry_lock:
        if _telemetry_instance is not None:
            return _telemetry_instance

        _telemetry_instance = LLMTelemetry()

    return _telemetry_instance


def init_telemetry(db_collection) -> LLMTelemetry:
    """Initialize telemetry with a MongoDB collection. Call once at startup."""
    global _telemetry_instance
    with _telemetry_lock:
        _telemetry_instance = LLMTelemetry(db_collection=db_collection)
    return _telemetry_instance
