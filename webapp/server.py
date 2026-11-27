"""SignalGuard local web app — Starlette backend.

Run:  python -m webapp            (then open http://127.0.0.1:8765)

Endpoints
    GET  /api/overview      configuration, dataset, headline metrics, evaluation status
    GET  /api/benchmarks    v0 / v2 metrics (mean, std, n) per split and gold version
    GET  /api/signals       frozen dataset with gold labels and latest v2 predictions
    POST /api/runs          start a pipeline run (one at a time) -> {job_id}
    GET  /api/runs/{id}     live status: stage, elapsed, digest when done
    GET  /api/runs          saved run history

Only Starlette + Uvicorn are used (already installed with Agno).
"""

from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
RESULTS = ROOT / "results" / "benchmark"
ARCHIVE = RESULTS / "v2_before_release_calibration"
DATASET = ROOT / "data" / "benchmark"
APP_RUNS = ROOT / "results" / "app_runs"

VERSIONS = ("v0", "v2")
STAGES = [
    ("load_signals", "raw_signals"),
    ("normalize", "signals"),
    ("profile_and_triage", "triage"),
    ("analysis", "relevance"),
    ("merge_assessments", "assessed"),
    ("synthesis", "digest"),
]


def _load(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _stem(version: str, split: str) -> str:
    return f"{version.replace('.', '_')}_{split}"


# --------------------------------------------------------------------------- benchmarks

def _summary(version: str, split: str, base: Path) -> Optional[Dict[str, Any]]:
    data = _load(base / f"{_stem(version, split)}_summary.json")
    label = version
    if data is None and version == "v2":
        archive_base = ARCHIVE if base == RESULTS else ARCHIVE / base.name
        data = _load(archive_base / f"{_stem(version, split)}_summary.json")
        label = "v2.0"
    if data is None:
        return None
    return {"version": version, "label": label, "runs": data.get("runs", 1),
            "gold_file": data.get("gold_file"), "metrics": data.get("metrics", {}),
            "archived": label == "v2.0"}


def benchmarks() -> Dict[str, Any]:
    out: Dict[str, Any] = {"gold": {}}
    for gold_name, base in (("v4", RESULTS), ("v4.1", RESULTS / "gold_v4_1")):
        if not base.exists():
            continue
        out["gold"][gold_name] = {
            split: [s for s in (_summary(v, split, base) for v in VERSIONS) if s] for split in ("dev", "test")
        }
    injection = _load(RESULTS / "injection_dev.json") or _load(ARCHIVE / "injection_dev.json")
    if injection:
        out["injection"] = {
            version: {k: v for k, v in data.items() if not k.endswith("_cases")}
            for version, data in injection["results"].items()
        }
        out["injection_cases"] = {v: d.get("risk_cases", []) for v, d in injection["results"].items()}
    return out


def evaluation_status() -> Dict[str, Any]:
    status: Dict[str, Any] = {"target_runs": 3, "items": []}
    for version in ("v2", "v0"):
        for split in ("dev", "test"):
            stem = _stem(version, split)
            done = 0
            while (RESULTS / f"{stem}_run{done + 1}.json").exists():
                done += 1
            partial = RESULTS / f"{stem}_run{done + 1}.partial.jsonl"
            in_progress = len(partial.read_text(encoding="utf-8").splitlines()) if partial.exists() else 0
            status["items"].append({"version": version, "split": split, "runs_done": done,
                                    "current_run_signals": in_progress,
                                    "signals": 48 if split == "dev" else 24})
    log = RESULTS / "run_log.txt"
    if log.exists():
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-1:]
        status["last_log_line"] = tail[0] if tail else ""
        status["log_updated"] = datetime.fromtimestamp(log.stat().st_mtime, timezone.utc).isoformat()
    return status


# --------------------------------------------------------------------------- signals explorer

def _latest_v2_records(split: str) -> Dict[str, Dict[str, Any]]:
    for path in (RESULTS / f"v2_{split}_run1.json", ARCHIVE / f"v2_{split}_run1.json"):
        data = _load(path)
        if data:
            return {r["signal_id"]: {**r, "_source_file": path.name} for r in data["records"]}
    return {}


def signals_payload() -> Dict[str, Any]:
    frozen = _load(DATASET / "signals_frozen.json") or []
    index = {f"{s['source']}:{s['id']}": s for s in frozen}
    rows: List[Dict[str, Any]] = []
    for split in ("dev", "test"):
        gold = _load(DATASET / f"{split}_gold_annotated_v4_1.json") or _load(DATASET / f"{split}_gold_annotated_v4.json")
        preds = _latest_v2_records(split)
        for g in (gold or {}).get("records", []):
            s = index.get(g["signal_id"], {})
            p = preds.get(g["signal_id"])
            rows.append({
                "signal_id": g["signal_id"], "split": split, "source": s.get("source"), "title": s.get("title"),
                "url": s.get("url"), "description": (s.get("description") or "")[:1200],
                "metadata": s.get("metadata", {}),
                "gold": {k: g.get(k) for k in ("relevance_score", "risk_level", "risk_category", "breaking_changes")},
                "gold_evidence": g.get("evidence"),
                "prediction": (p or {}).get("predictions"),
                "v2": (p or {}).get("v2"),
                "prediction_file": (p or {}).get("_source_file"),
            })
    return {"signals": rows}


# --------------------------------------------------------------------------- pipeline jobs

class Job:
    def __init__(self, params: Dict[str, Any]):
        self.id = uuid.uuid4().hex[:10]
        self.params = params
        self.state: Dict[str, Any] = {}
        self.status = "queued"
        self.error: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.started = time.time()
        self.finished: Optional[float] = None

    def stage(self) -> Dict[str, Any]:
        reached = [name for name, key in STAGES if key in self.state]
        return {"completed": reached, "current": STAGES[len(reached)][0] if len(reached) < len(STAGES) else None}

    def to_dict(self, full: bool = False) -> Dict[str, Any]:
        data = {"job_id": self.id, "status": self.status, "params": self.params, "error": self.error,
                "elapsed_s": round((self.finished or time.time()) - self.started, 1),
                "stage": self.stage(), "triage": self.state.get("triage")}
        if full and self.result is not None:
            data["result"] = self.result
        return data


JOBS: Dict[str, Job] = {}
RUN_LOCK = threading.Lock()


def _serialisable_signal(s: Dict[str, Any]) -> Dict[str, Any]:
    rel, risk = s.get("relevance", {}), s.get("risk", {})
    return {
        "signal_id": f"{s.get('source')}:{s.get('id')}", "source": s.get("source"), "title": s.get("title"),
        "url": s.get("url"), "description": (s.get("description") or "")[:600],
        "relevance": {k: rel.get(k) for k in ("score", "novelty", "technical_relevance", "applicability",
                                               "timeliness", "reasoning", "used_fallback", "adjustments")},
        "risk": {k: risk.get(k) for k in ("risk_level", "risk_category", "breaking_changes", "concerns", "evidence",
                                           "evidence_strength", "adjustments", "llm_view", "rejected_evidence",
                                           "used_fallback", "triaged")},
        "profile": risk.get("profile") or rel.get("profile"),
        "metadata": {k: v for k, v in (s.get("metadata") or {}).items()
                     if k in ("published", "published_at", "created_at", "stars", "downloads", "points", "comments",
                              "repository", "tag_name", "author", "language", "likes")},
        "collected_at": s.get("collected_at"),
    }


# --------------------------------------------------------------------------- news feed

RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
DATE_KEYS = ("published_at", "published", "created_at")


def _feed_item(sig: Dict[str, Any], origin: str, assessed_at: Optional[str], run_id: Optional[str]) -> Dict[str, Any]:
    meta = sig.get("metadata") or {}
    risk = sig.get("risk") or {}
    return {
        **sig,
        "origin": origin,
        "run_id": run_id,
        "assessed_at": assessed_at,
        "published": next((str(meta[k]) for k in DATE_KEYS if meta.get(k)), None),
        "risk_rank": RISK_RANK.get(risk.get("risk_level") or "LOW", 0),
        "elevated_risk": RISK_RANK.get(risk.get("risk_level") or "LOW", 0) >= 1 or bool(risk.get("breaking_changes")),
    }


def feed_payload() -> Dict[str, Any]:
    """Every assessed signal, newest assessment wins, ranked by relevance.

    Sources: analyses launched from the app (results/app_runs, newest first),
    then the frozen reference dataset with the latest saved v2 predictions.
    High-risk signals are kept and flagged, never filtered out.
    """
    items: Dict[str, Dict[str, Any]] = {}
    runs = 0
    if APP_RUNS.exists():
        for path in sorted(APP_RUNS.glob("*.json"), reverse=True):
            data = _load(path) or {}
            result = data.get("result") or {}
            if not result.get("signals"):
                continue
            runs += 1
            stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            origin = "live" if (data.get("params") or {}).get("mode") == "live" else "analyse"
            for sig in result["signals"]:
                items.setdefault(sig["signal_id"], _feed_item(sig, origin, stamp, data.get("job_id")))
    dataset = 0
    frozen = {f"{s['source']}:{s['id']}": s for s in (_load(DATASET / "signals_frozen.json") or [])}
    for split in ("dev", "test"):
        for sid, rec in _latest_v2_records(split).items():
            if sid in items or sid not in frozen:
                continue
            s, p, v2 = frozen[sid], rec.get("predictions") or {}, rec.get("v2") or {}
            sig = {
                "signal_id": sid, "source": s.get("source"), "title": s.get("title"), "url": s.get("url"),
                "description": (s.get("description") or "")[:600],
                "relevance": {"score": p.get("relevance_score"), "reasoning": p.get("relevance_reasoning"),
                              **(p.get("relevance_rubric") or {}), "adjustments": v2.get("relevance_adjustments")},
                "risk": {"risk_level": p.get("risk_level"), "risk_category": p.get("risk_category"),
                         "breaking_changes": p.get("breaking_changes"), "concerns": p.get("concerns"),
                         "evidence": p.get("evidence"), "evidence_strength": p.get("evidence_strength"),
                         "adjustments": v2.get("risk_adjustments"), "llm_view": v2.get("llm_view"),
                         "rejected_evidence": v2.get("rejected_evidence")},
                "profile": v2.get("profile"),
                "metadata": {k: v for k, v in (s.get("metadata") or {}).items() if k in
                             ("published", "published_at", "created_at", "stars", "downloads", "points", "comments",
                              "repository", "tag_name", "author", "language", "likes")},
                "collected_at": s.get("collected_at"),
            }
            items[sid] = _feed_item(sig, "dataset", rec.get("_source_file"), None)
            dataset += 1
    ranked = sorted(items.values(), key=lambda i: (-(i["relevance"].get("score") or 0), -i["risk_rank"]))
    return {"items": ranked, "counts": {"total": len(ranked), "from_runs": len(ranked) - dataset,
                                        "from_dataset": dataset, "runs": runs,
                                        "elevated_risk": sum(1 for i in ranked if i["elevated_risk"])}}


def _execute(job: Job) -> None:
    import main as cli

    p = job.params
    try:
        job.status = "running"
        if p["version"] == "v2":
            from agents.v2 import RelevanceAgentV2, ResponseCache, RiskAgentV2
            from agents.v2.synthesis import SynthesisAgentV2
            from pipeline.workflow import build_workflow

            cache = ResponseCache()
            model = p.get("model") or None
            workflow = build_workflow(
                RelevanceAgentV2(model_id=model, cache=cache), RiskAgentV2(model_id=model, cache=cache),
                SynthesisAgentV2(model_id=model, cache=cache), collect_live=cli.collect_signals,
            )
            options = {"llm_synthesis": p["llm_synthesis"], "concurrency": 4, "limit_per_source": p["limit"]}
            if p["mode"] == "frozen":
                options.update(frozen_path=str(cli.FROZEN_SIGNALS), split=p.get("split"),
                               max_signals=p.get("max_signals"))
            output = workflow.run(input="run signalguard pipeline", additional_data=options,
                                  session_state=job.state)
            digest = job.state.get("digest") or output.content
            assessed = job.state.get("assessed", [])
        else:
            from pipeline.workflow import load_frozen

            raw = (load_frozen(cli.FROZEN_SIGNALS, p.get("split"), p.get("max_signals")) if p["mode"] == "frozen"
                   else cli.collect_signals(p["limit"]))
            job.state["raw_signals"] = raw
            result = cli.run_legacy(p["version"], raw)
            job.state.update(signals=raw, triage=None, relevance=True, assessed=result["assessed"])
            digest, assessed = result["digest"], result["assessed"]
            job.state["digest"] = digest
        if not isinstance(digest, dict):
            raise RuntimeError(f"Pipeline did not return a digest: {str(digest)[:300]}")
        signals = [_serialisable_signal(s) for s in assessed]
        job.result = {
            "digest": {k: v for k, v in digest.items() if k not in ("priority_signals", "signals_by_source")},
            "priority_ids": [f"{s.get('source')}:{s.get('id')}" for s in digest.get("priority_signals", [])],
            "signals": signals,
            "fallbacks": sum(bool(s["relevance"].get("used_fallback")) + bool(s["risk"].get("used_fallback"))
                             for s in signals),
            "triage": job.state.get("triage"),
        }
        job.status = "done"
    except BaseException as exc:  # QuotaExhausted derives from BaseException
        job.status = "error"
        name = type(exc).__name__
        job.error = ("Quota du fournisseur épuisé. Réessaie plus tard ou choisis un autre modèle. " + str(exc)[:300]
                     if name == "QuotaExhausted" else f"{name}: {exc}")
        traceback.print_exc()
    finally:
        job.finished = time.time()
        RUN_LOCK.release()
        if job.result is not None:
            APP_RUNS.mkdir(parents=True, exist_ok=True)
            (APP_RUNS / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{job.id}.json").write_text(
                json.dumps(job.to_dict(full=True), ensure_ascii=False, default=str, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------- routes

async def index(_: Request) -> FileResponse:
    return FileResponse(STATIC / "index.html")


async def api_overview(_: Request) -> JSONResponse:
    import config

    frozen = _load(DATASET / "signals_frozen.json") or []
    sources: Dict[str, int] = {}
    for s in frozen:
        sources[s["source"]] = sources.get(s["source"], 0) + 1
    tests = sum(t.count("    def test_") for t in
                (p.read_text(encoding="utf-8") for p in (ROOT / "tests").glob("test_*.py")))
    return JSONResponse({
        "provider": config.LLM_PROVIDER,
        "models": {"relevance": config.MODEL_RELEVANCE, "risk": config.MODEL_RISK,
                   "synthesis": config.MODEL_SYNTHESIS},
        "api_key": bool(config.LLM_API_KEY),
        "max_rpm": config.LLM_MAX_RPM,
        "dataset": {"signals": len(frozen), "sources": sources, "dev": 48, "test": 24},
        "tests": tests,
        "evaluation": evaluation_status(),
        "busy": RUN_LOCK.locked(),
    })


async def api_benchmarks(_: Request) -> JSONResponse:
    return JSONResponse(benchmarks())


async def api_signals(_: Request) -> JSONResponse:
    return JSONResponse(signals_payload())


async def api_start_run(request: Request) -> JSONResponse:
    body = await request.json()
    params = {
        "version": body.get("version", "v2") if body.get("version") in VERSIONS else "v2",
        "mode": "live" if body.get("mode") == "live" else "frozen",
        "split": body.get("split") if body.get("split") in ("dev", "test") else None,
        "max_signals": max(1, min(int(body.get("max_signals") or 8), 72)),
        "limit": max(1, min(int(body.get("limit") or 3), 10)),
        "llm_synthesis": bool(body.get("llm_synthesis", True)),
        "model": (body.get("model") or "").strip() or None,
    }
    if not RUN_LOCK.acquire(blocking=False):
        return JSONResponse({"error": "Une analyse est déjà en cours."}, status_code=409)
    job = Job(params)
    JOBS[job.id] = job
    threading.Thread(target=_execute, args=(job,), daemon=True).start()
    return JSONResponse({"job_id": job.id})


async def api_get_run(request: Request) -> JSONResponse:
    job = JOBS.get(request.path_params["job_id"])
    if job is None:
        saved = next(APP_RUNS.glob(f"*_{request.path_params['job_id']}.json"), None) if APP_RUNS.exists() else None
        return JSONResponse(_load(saved) if saved else {"error": "unknown job"}, status_code=200 if saved else 404)
    return JSONResponse(json.loads(json.dumps(job.to_dict(full=True), default=str)))


async def api_feed(_: Request) -> JSONResponse:
    return JSONResponse(json.loads(json.dumps(feed_payload(), default=str)))


async def api_list_runs(_: Request) -> JSONResponse:
    runs = []
    if APP_RUNS.exists():
        for path in sorted(APP_RUNS.glob("*.json"), reverse=True)[:20]:
            data = _load(path) or {}
            digest = (data.get("result") or {}).get("digest", {})
            runs.append({"job_id": data.get("job_id"), "file": path.name, "params": data.get("params"),
                         "elapsed_s": data.get("elapsed_s"), "total_signals": digest.get("total_signals"),
                         "synthesis": (digest.get("synthesis") or {}).get("mode")})
    return JSONResponse({"runs": runs})


class NoCacheMiddleware:
    """Local app: always serve the latest HTML/CSS/JS after an edit."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        async def send_no_cache(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in (b"etag", b"last-modified")]
                headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.inner(scope, receive, send_no_cache if scope["type"] == "http" else send)


app = Starlette(routes=[
    Route("/", index),
    Route("/api/overview", api_overview),
    Route("/api/benchmarks", api_benchmarks),
    Route("/api/signals", api_signals),
    Route("/api/feed", api_feed),
    Route("/api/runs", api_start_run, methods=["POST"]),
    Route("/api/runs", api_list_runs, methods=["GET"]),
    Route("/api/runs/{job_id}", api_get_run),
    Mount("/static", StaticFiles(directory=STATIC), name="static"),
])

app.add_middleware(NoCacheMiddleware)
