"""
Shared async LLM call infrastructure for all engines.

Supports:
  - Robust JSON repair (code fences, trailing commas, markdown wrapping)
  - Optional Pydantic schema validation
  - Model-fallback loop with retry
  - Plain-text mode for engines like HintGenerator
  - Response caching (when cache_key is provided)
  - Per-call telemetry (latency, tokens, success/failure)
"""

import asyncio
import json
import random
import re
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Type

from langchain_core.messages import HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ValidationError

from adaptive.core.llm_cache import get_llm_cache
from adaptive.core.llm_registry import get_llm_config, get_tier_for_engine, mark_cooldown
from adaptive.core.llm_telemetry import get_telemetry

logger = logging.getLogger("llm_utils")


# ----------------------------------
# BACKOFF HELPERS
# ----------------------------------

def _get_retry_config() -> dict:
    """Return retry config from llm config, with defaults."""
    cfg = get_llm_config()
    retry = cfg.get("retry", {})
    return {
        "backoff_base": retry.get("backoff_base", 0.5),
        "backoff_cap": retry.get("backoff_cap", 8.0),
        "rate_limit_cooldown": retry.get("rate_limit_cooldown", 30.0),
    }


def _get_hedge_config() -> dict:
    """Hedged-request config: race the first N keys in parallel, first valid wins.
    Cuts tail latency at the cost of extra calls, so default OFF."""
    hedge = get_llm_config().get("hedge", {})
    return {
        "enabled": bool(hedge.get("enabled", False)),
        "n": int(hedge.get("n", 2)),
        "tiers": set(hedge.get("tiers", ["strong"])),
    }


def _is_rate_limit(exc: Exception) -> bool:
    """Detect rate-limit / 429 errors across LangChain provider wrappers."""
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg and "limit" in msg:
        return True
    if "too many requests" in msg:
        return True
    # Some providers wrap the status code in an attribute
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status == 429:
        return True
    return False


async def _backoff_sleep(attempt: int, base: float, cap: float) -> None:
    """Sleep with exponential backoff + jitter, capped at `cap` seconds."""
    delay = min(base * (2 ** attempt), cap)
    jitter = random.uniform(0, delay * 0.5)
    await asyncio.sleep(delay + jitter)


# ----------------------------------
# TOKEN EXTRACTION HELPER
# ----------------------------------

def _extract_tokens(response) -> Tuple[Optional[int], Optional[int]]:
    """Extract token counts from LangChain response if available."""
    tokens_in = None
    tokens_out = None

    # LangChain AIMessage.usage_metadata (Gemini, OpenAI, Mistral)
    usage = getattr(response, "usage_metadata", None)
    if usage:
        tokens_in = getattr(usage, "input_tokens", None) or usage.get("input_tokens") if isinstance(usage, dict) else getattr(usage, "input_tokens", None)
        tokens_out = getattr(usage, "output_tokens", None) or usage.get("output_tokens") if isinstance(usage, dict) else getattr(usage, "output_tokens", None)

    # Fallback: response_metadata.token_usage (Groq, some providers)
    if tokens_in is None:
        meta = getattr(response, "response_metadata", {})
        if isinstance(meta, dict):
            tu = meta.get("token_usage") or meta.get("usage", {})
            if isinstance(tu, dict):
                tokens_in = tu.get("prompt_tokens") or tu.get("input_tokens")
                tokens_out = tu.get("completion_tokens") or tu.get("output_tokens")

    return tokens_in, tokens_out


# ----------------------------------
# ROBUST JSON PARSER
# ----------------------------------

def parse_json_robust(text: str) -> Optional[Dict]:
    """
    Extract and parse JSON from LLM output.

    Handles: clean JSON, markdown code fences, prose wrapping,
    trailing commas, single-quoted strings.
    """
    if not text:
        return None

    # 1. Direct parse (fast path)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Strip markdown code fences
    cleaned = text
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. Extract first { ... } block
    brace_start = cleaned.find("{")
    if brace_start == -1:
        return None

    depth = 0
    brace_end = -1
    for i in range(brace_start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                brace_end = i + 1
                break

    if brace_end == -1:
        brace_end = cleaned.rfind("}") + 1

    if brace_end <= brace_start:
        return None

    candidate = cleaned[brace_start:brace_end]

    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        pass

    # 4. Fix trailing commas
    fixed = re.sub(r',\s*([}\]])', r'\1', candidate)
    try:
        return json.loads(fixed)
    except (json.JSONDecodeError, ValueError):
        pass

    # 5. Single quotes -> double quotes
    try:
        return json.loads(candidate.replace("'", '"'))
    except (json.JSONDecodeError, ValueError):
        pass

    return None


# ----------------------------------
# CIRCUIT BREAKER
# ----------------------------------

class CircuitBreaker:
    """
    Per-model circuit breaker. Opens after `threshold` consecutive failures,
    stays open for `cooldown_sec`, then allows one half-open probe.
    """
    _instances: Dict[str, "CircuitBreaker"] = {}

    def __init__(self, model_name: str, threshold: int = 5, cooldown_sec: float = 60.0):
        self.model_name = model_name
        self.threshold = threshold
        self.cooldown_sec = cooldown_sec
        self.failures = 0
        self.opened_at: Optional[float] = None
        self.state = "closed"  # closed | open | half_open

    @classmethod
    def for_model(cls, model_name: str) -> "CircuitBreaker":
        if model_name not in cls._instances:
            cls._instances[model_name] = cls(model_name)
        return cls._instances[model_name]

    def allow_request(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - (self.opened_at or 0) >= self.cooldown_sec:
                self.state = "half_open"
                logger.info("Circuit half-open for %s — allowing probe", self.model_name)
                return True
            return False
        # half_open — allow one probe
        return True

    def record_success(self):
        if self.state == "half_open":
            logger.info("Circuit closed for %s — probe succeeded", self.model_name)
        self.failures = 0
        self.state = "closed"
        self.opened_at = None

    def record_failure(self):
        self.failures += 1
        if self.state == "half_open" or self.failures >= self.threshold:
            self.state = "open"
            self.opened_at = time.time()
            logger.warning(
                "Circuit OPEN for %s — %d consecutive failures, cooldown %.0fs",
                self.model_name, self.failures, self.cooldown_sec,
            )


# Per-call timeout (seconds). Prevents hanging on slow providers.
LLM_CALL_TIMEOUT = 45.0


# ----------------------------------
# ASYNC LLM CALL WITH MODEL FALLBACK
# ----------------------------------

async def _hedged_call(
    models: List[Tuple[str, BaseChatModel]],
    prompt: str,
    required_key: str,
    schema: Optional[Type[BaseModel]],
    engine_name: str,
    prompt_version: str,
    telemetry,
    retry_cfg: dict,
) -> Optional[Dict]:
    """Race the given models in parallel; return the first valid parsed dict and
    cancel the rest. Returns None if all fail. Single-shot per model (no retries)
    — retries/circuit-breaker live in the sequential fallback path."""
    async def _one(model_name, model):
        record = telemetry.start(engine_name, model_name, prompt_version)
        try:
            response = await asyncio.wait_for(
                model.ainvoke([HumanMessage(content=prompt)]),
                timeout=LLM_CALL_TIMEOUT,
            )
            text = response.content.strip()
            tokens_in, tokens_out = _extract_tokens(response)
            data = parse_json_robust(text)
            if data is None or required_key not in data:
                telemetry.finish(record, ok=False, tokens_in=tokens_in, tokens_out=tokens_out, error="parse_or_key_missing")
                return None
            if schema is not None:
                try:
                    schema.model_validate(data)
                except ValidationError:
                    telemetry.finish(record, ok=False, tokens_in=tokens_in, tokens_out=tokens_out, error="schema_validation")
                    return None
            data["model_used"] = model_name
            telemetry.finish(record, ok=True, tokens_in=tokens_in, tokens_out=tokens_out)
            return data
        except asyncio.CancelledError:
            telemetry.finish(record, ok=False, error="hedge_cancelled")
            raise
        except Exception as e:
            telemetry.finish(record, ok=False, error=str(e)[:200])
            if _is_rate_limit(e):
                mark_cooldown(model_name, retry_cfg["rate_limit_cooldown"])
            return None

    tasks = [asyncio.create_task(_one(n, m)) for n, m in models]
    winner: Optional[Dict] = None
    pending = set(tasks)
    try:
        while pending and winner is None:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                try:
                    r = d.result()
                except Exception:
                    r = None
                if r is not None:
                    winner = r
                    break
    finally:
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    return winner


async def call_llm(
    models: List[Tuple[str, BaseChatModel]],
    prompt: str,
    required_key: str,
    schema: Optional[Type[BaseModel]] = None,
    retries: Optional[int] = None,
    cache_key: Optional[str] = None,
    force_fresh: bool = False,
    engine_name: str = "unknown",
    prompt_version: str = "v1",
) -> Optional[Dict]:
    """
    Async LLM call with model-fallback, JSON parsing, caching, and telemetry.

    Args:
        models: List of (name, model) tuples from build_models()
        prompt: The prompt to send
        required_key: Key that must be present in parsed JSON
        schema: Optional Pydantic model for validation
        retries: Retries per model (default from config)
        cache_key: If provided, check/store in LLM cache
        force_fresh: Skip cache lookup (still stores result)
        engine_name: For telemetry tagging (e.g. "explainer", "question_generator")
        prompt_version: For telemetry and cache key tracking

    Returns:
        Parsed dict with "model_used" key, or None if all fail.
    """
    if retries is None:
        retries = get_llm_config().get("max_retries", 3)

    # Check cache
    cache = get_llm_cache()
    if cache and cache_key and not force_fresh:
        cached = cache.get(cache_key)
        if cached is not None:
            cached["_cached"] = True
            return cached

    telemetry = get_telemetry()
    retry_cfg = _get_retry_config()

    # Hedged race (opt-in): fire first N keys in parallel, first valid wins.
    # Cuts tail latency for latency-critical (strong) engines. All-fail → falls
    # through to the sequential fallback loop below.
    hedge_cfg = _get_hedge_config()
    if (hedge_cfg["enabled"] and len(models) >= 2
            and get_tier_for_engine(engine_name) in hedge_cfg["tiers"]):
        n = max(2, min(hedge_cfg["n"], len(models)))
        hedged = await _hedged_call(
            models[:n], prompt, required_key, schema,
            engine_name, prompt_version, telemetry, retry_cfg,
        )
        if hedged is not None:
            if cache and cache_key:
                cache.put(cache_key, hedged)
            return hedged

    # LLM fallback loop with circuit breaker + timeout
    for model_name, model in models:
        cb = CircuitBreaker.for_model(model_name)
        if not cb.allow_request():
            logger.info("Circuit open for %s — skipping", model_name)
            continue

        for attempt in range(retries):
            record = telemetry.start(engine_name, model_name, prompt_version)
            try:
                response = await asyncio.wait_for(
                    model.ainvoke([HumanMessage(content=prompt)]),
                    timeout=LLM_CALL_TIMEOUT,
                )
                text = response.content.strip()

                tokens_in, tokens_out = _extract_tokens(response)

                data = parse_json_robust(text)

                if data is None or required_key not in data:
                    telemetry.finish(record, ok=False, tokens_in=tokens_in, tokens_out=tokens_out, error="parse_or_key_missing")
                    if attempt < retries - 1:
                        await _backoff_sleep(attempt, retry_cfg["backoff_base"], retry_cfg["backoff_cap"])
                    continue

                # Optional schema validation
                if schema is not None:
                    try:
                        schema.model_validate(data)
                    except ValidationError as ve:
                        logger.warning(
                            "Schema validation failed for %s attempt %d: %s",
                            model_name, attempt + 1, ve.error_count()
                        )
                        telemetry.finish(record, ok=False, tokens_in=tokens_in, tokens_out=tokens_out, error="schema_validation")
                        if attempt < retries - 1:
                            await _backoff_sleep(attempt, retry_cfg["backoff_base"], retry_cfg["backoff_cap"])
                        continue

                data["model_used"] = model_name
                telemetry.finish(record, ok=True, tokens_in=tokens_in, tokens_out=tokens_out)
                cb.record_success()

                # Store in cache
                if cache and cache_key:
                    cache.put(cache_key, data)

                return data

            except asyncio.TimeoutError:
                telemetry.finish(record, ok=False, error="timeout")
                logger.warning("%s timed out after %.0fs (attempt %d)", model_name, LLM_CALL_TIMEOUT, attempt + 1)
                cb.record_failure()
                break  # timeout = skip model entirely

            except Exception as e:
                telemetry.finish(record, ok=False, error=str(e)[:200])
                cb.record_failure()
                if _is_rate_limit(e):
                    mark_cooldown(model_name, retry_cfg["rate_limit_cooldown"])
                    logger.warning(
                        "%s rate-limited (attempt %d) — cooldown %.0fs, next model",
                        model_name, attempt + 1, retry_cfg["rate_limit_cooldown"],
                    )
                    break  # skip remaining retries, move to next model
                logger.warning("%s attempt %d failed: %s", model_name, attempt + 1, e)
                if attempt < retries - 1:
                    await _backoff_sleep(attempt, retry_cfg["backoff_base"], retry_cfg["backoff_cap"])

    return None


# ----------------------------------
# ASYNC LLM CALL FOR PLAIN TEXT
# ----------------------------------

async def call_llm_text(
    models: List[Tuple[str, BaseChatModel]],
    prompt: str,
    min_length: int = 10,
    retries: Optional[int] = None,
    engine_name: str = "unknown",
    prompt_version: str = "v1",
) -> Optional[str]:
    """
    Async LLM call returning plain text (no JSON parsing).
    Used by engines like HintGenerator.
    """
    if retries is None:
        retries = get_llm_config().get("max_retries", 3)

    telemetry = get_telemetry()
    retry_cfg = _get_retry_config()

    for model_name, model in models:
        cb = CircuitBreaker.for_model(model_name)
        if not cb.allow_request():
            logger.info("Circuit open for %s — skipping", model_name)
            continue

        for attempt in range(retries):
            record = telemetry.start(engine_name, model_name, prompt_version)
            try:
                response = await asyncio.wait_for(
                    model.ainvoke([HumanMessage(content=prompt)]),
                    timeout=LLM_CALL_TIMEOUT,
                )
                text = response.content.strip()

                tokens_in, tokens_out = _extract_tokens(response)

                if text and len(text) >= min_length:
                    telemetry.finish(record, ok=True, tokens_in=tokens_in, tokens_out=tokens_out)
                    cb.record_success()
                    return text

                telemetry.finish(record, ok=False, tokens_in=tokens_in, tokens_out=tokens_out, error="too_short")
                if attempt < retries - 1:
                    await _backoff_sleep(attempt, retry_cfg["backoff_base"], retry_cfg["backoff_cap"])

            except asyncio.TimeoutError:
                telemetry.finish(record, ok=False, error="timeout")
                logger.warning("%s timed out after %.0fs (attempt %d)", model_name, LLM_CALL_TIMEOUT, attempt + 1)
                cb.record_failure()
                break

            except Exception as e:
                telemetry.finish(record, ok=False, error=str(e)[:200])
                cb.record_failure()
                if _is_rate_limit(e):
                    logger.warning(
                        "%s rate-limited (attempt %d) — skipping to next model",
                        model_name, attempt + 1,
                    )
                    break
                logger.warning("%s attempt %d failed: %s", model_name, attempt + 1, e)
                if attempt < retries - 1:
                    await _backoff_sleep(attempt, retry_cfg["backoff_base"], retry_cfg["backoff_cap"])

    return None
