from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_ms: int
    end_ms: Optional[int] = None
    prompt_hash: Optional[str] = None
    output_hash: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    def close(self, output: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self.end_ms = int(time.time() * 1000)
        self.output_hash = _sha256(output)
        if meta:
            self.meta = {**(self.meta or {}), **meta}


class Logger:
    """Simple JSONL logger: Logs (diary) + Traces (narrative)."""

    def __init__(self, logs_dir: str) -> None:
        self.logs_path = Path(logs_dir) / "events.jsonl"
        self.logs_path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event: Dict[str, Any]) -> None:
        with self.logs_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


class Metrics:
    """In-memory metrics aggregator (health report)."""

    def __init__(self) -> None:
        self.counters: Dict[str, int] = {}
        self.timers_ms: Dict[str, list[int]] = {}
        self.gauges: Dict[str, float] = {}

    def inc(self, name: str, n: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + n

    def observe_ms(self, name: str, ms: int) -> None:
        self.timers_ms.setdefault(name, []).append(ms)

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = float(value)

    def snapshot(self) -> Dict[str, Any]:
        def summary(vals: list[int]) -> Dict[str, float]:
            if not vals:
                return {"count": 0, "mean_ms": 0.0, "p95_ms": 0.0}
            s = sorted(vals)
            p95 = s[int(0.95 * (len(s) - 1))]
            return {
                "count": len(vals),
                "mean_ms": sum(vals) / len(vals),
                "p95_ms": float(p95),
            }

        return {
            "counters": dict(self.counters),
            "timers": {k: summary(v) for k, v in self.timers_ms.items()},
            "gauges": dict(self.gauges),
        }


@dataclass
class TraceContext:
    trace_id: str

    def child_span(self, name: str, parent_span_id: Optional[str] = None) -> Span:
        span_id = _sha256(f"{self.trace_id}:{name}:{time.time()}")[:16]
        return Span(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            start_ms=int(time.time() * 1000),
        )


def record_span(logger: Logger, metrics: Metrics, span: Span, prompt: str, output: str) -> None:
    span.prompt_hash = _sha256(prompt)
    if span.end_ms is None:
        span.close(output)
    duration = int(span.end_ms - span.start_ms) if span.end_ms else 0
    metrics.observe_ms(f"span.{span.name}.latency", duration)
    logger.event({"type": "span", **asdict(span), "duration_ms": duration})
