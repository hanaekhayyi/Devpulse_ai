"""Reliability layer for structured LLM calls (SignalGuard v2).

Responsibilities:
- deterministic decoding (temperature 0 + fixed seed);
- Agno ``output_schema`` with Pydantic validation;
- retries with exponential backoff and jitter, covering both transport errors
  *and* schema-invalid answers (Agno's own ``retries`` only re-runs on raised
  exceptions; an answer that fails validation comes back as a normal run);
- a content-addressed disk cache so benchmarks are reproducible and free to
  re-run;
- per-call accounting: attempts, latency, tokens and provider-reported cost.

A fresh Agno ``Agent`` is built per attempt, which keeps the runner safe to use
from a thread pool (Agno agents hold per-run state).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError

from agents.v2.ratelimit import QuotaExhausted, RateLimiter, global_limiter, is_rate_limit_error

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / ".cache" / "llm"


@dataclass
class CallStats:
    attempts: int = 0
    cache_hit: bool = False
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CallResult:
    output: Optional[BaseModel]
    stats: CallStats

    @property
    def ok(self) -> bool:
        return self.output is not None


class ResponseCache:
    """Thread-safe JSON cache addressed by a SHA-256 key."""

    def __init__(self, directory: Path = DEFAULT_CACHE_DIR):
        self.directory = Path(directory)
        self._lock = threading.Lock()

    def _path(self, key: str) -> Path:
        return self.directory / key[:2] / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, key: str, value: Dict[str, Any]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        with self._lock:
            os.replace(tmp, path)


def _default_agent_factory(**kwargs: Any) -> Any:
    from agno.agent import Agent
    from agno.models.openai import OpenAIChat

    from config import LLM_API_KEY, LLM_BASE_URL, LLM_SEED_PARAM, SYSTEM_ROLE_MAP

    seed_kwargs: Dict[str, Any] = (
        {"seed": kwargs["seed"]} if LLM_SEED_PARAM == "seed" else {"extra_body": {LLM_SEED_PARAM: kwargs["seed"]}}
    )
    model = OpenAIChat(
        id=kwargs["model_id"],
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=kwargs["temperature"],
        timeout=kwargs["timeout"],
        role_map=SYSTEM_ROLE_MAP,
        **seed_kwargs,
    )
    return Agent(
        name=kwargs["name"],
        model=model,
        instructions=kwargs["instructions"],
        output_schema=kwargs["schema"],
        markdown=False,
        telemetry=False,
    )


def _extract_json(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text


class StructuredLLM:
    """Run one structured prompt reliably and return a validated Pydantic object."""

    def __init__(
        self,
        *,
        name: str,
        instructions: List[str],
        schema: Type[BaseModel],
        model_id: str,
        prompt_version: str,
        temperature: float = 0.0,
        seed: int = 42,
        max_attempts: int = 4,
        base_delay_s: float = 1.0,
        timeout_s: float = 60.0,
        cache: Optional[ResponseCache] = None,
        agent_factory: Callable[..., Any] = _default_agent_factory,
        sleep: Callable[[float], None] = time.sleep,
        limiter: Optional[RateLimiter] = None,
    ):
        self.name = name
        self.instructions = instructions
        self.schema = schema
        self.model_id = model_id
        self.prompt_version = prompt_version
        self.temperature = temperature
        self.seed = seed
        self.max_attempts = max_attempts
        self.base_delay_s = base_delay_s
        self.timeout_s = timeout_s
        self.cache = cache
        self.agent_factory = agent_factory
        self.sleep = sleep
        self.limiter = limiter

    def cache_key(self, prompt: str, salt: str = "") -> str:
        payload = json.dumps(
            {
                "model": self.model_id,
                "prompt_version": self.prompt_version,
                "instructions": self.instructions,
                "schema": self.schema.model_json_schema(),
                "temperature": self.temperature,
                "seed": self.seed,
                "prompt": prompt,
                "salt": salt,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _coerce(self, content: Any) -> BaseModel:
        if isinstance(content, self.schema):
            return content
        if isinstance(content, dict):
            return self.schema.model_validate(content)
        if isinstance(content, str):
            return self.schema.model_validate_json(_extract_json(content))
        raise ValueError(f"Unexpected response type: {type(content).__name__}")

    def run(self, prompt: str, *, cache_salt: str = "") -> CallResult:
        stats = CallStats()
        started = time.perf_counter()
        key = self.cache_key(prompt, cache_salt) if self.cache else None

        if self.cache and key:
            cached = self.cache.get(key)
            if cached is not None:
                try:
                    output = self.schema.model_validate(cached["output"])
                    stats.cache_hit = True
                    stats.input_tokens = cached.get("input_tokens", 0)
                    stats.output_tokens = cached.get("output_tokens", 0)
                    stats.cost_usd = cached.get("cost_usd", 0.0)
                    stats.latency_ms = round((time.perf_counter() - started) * 1000, 2)
                    return CallResult(output, stats)
                except (KeyError, ValidationError):
                    pass

        output: Optional[BaseModel] = None
        for attempt in range(self.max_attempts):
            stats.attempts = attempt + 1
            try:
                (self.limiter or global_limiter(self.model_id)).acquire()
                agent = self.agent_factory(
                    name=self.name,
                    instructions=self.instructions,
                    schema=self.schema,
                    model_id=self.model_id,
                    temperature=self.temperature,
                    seed=self.seed,
                    timeout=self.timeout_s,
                )
                response = agent.run(prompt, stream=False)
                metrics = getattr(response, "metrics", None)
                if metrics is not None:
                    stats.input_tokens += int(getattr(metrics, "input_tokens", 0) or 0)
                    stats.output_tokens += int(getattr(metrics, "output_tokens", 0) or 0)
                    stats.cost_usd += float(getattr(metrics, "cost", 0.0) or 0.0)
                status = str(getattr(response, "status", "completed")).lower()
                if "error" in status:
                    raise RuntimeError(f"run status {status}: {str(response.content)[:200]}")
                output = self._coerce(response.content)
                break
            except (ValidationError, ValueError, RuntimeError, Exception) as exc:  # noqa: BLE001
                stats.errors.append(f"attempt {attempt + 1}: {type(exc).__name__}: {str(exc)[:200]}")
                if attempt < self.max_attempts - 1:
                    delay = self.base_delay_s * (2**attempt) + random.uniform(0, self.base_delay_s / 2)
                    if is_rate_limit_error(exc):
                        delay = min(60.0, max(delay, 10.0 * (2**attempt)))
                    self.sleep(delay)

        stats.latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if output is None and stats.errors and all(is_rate_limit_error(e) for e in stats.errors):
            raise QuotaExhausted(f"{self.model_id}: {stats.errors[-1]}")
        if output is not None and self.cache and key:
            self.cache.set(
                key,
                {
                    "output": output.model_dump(),
                    "input_tokens": stats.input_tokens,
                    "output_tokens": stats.output_tokens,
                    "cost_usd": stats.cost_usd,
                },
            )
        return CallResult(output, stats)
