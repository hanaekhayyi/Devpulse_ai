"""SignalGuard v2 pipeline as an Agno Workflow.

    load_signals -> normalize -> profile_and_triage
        -> Parallel(score_relevance, assess_risk_llm, assess_risk_fast_path)
        -> merge_assessments
        -> Condition(has_signals)
              true : Router(synthesis_router) -> llm_synthesis | deterministic_synthesis
              false: empty_digest

Shared data lives in the workflow ``session_state`` (via ``run_context``):
each step reads what it needs and writes its own keys, so the parallel steps
never write the same key. Agents are injected, which keeps the workflow
testable without any LLM call.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agno.run import RunContext
from agno.workflow import Condition, Parallel, Router, Step, StepInput, StepOutput, Workflow

from agents.signal_collector import SignalCollector
from agents.v2.profiler import profile_signal
from agents.v2.triage import fast_path_risk, needs_llm_risk

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _opts(step_input: StepInput) -> Dict[str, Any]:
    return step_input.additional_data or {}


def _parallel_map(fn: Callable[[Dict[str, Any]], Any], items: List[Dict[str, Any]], workers: int) -> List[Any]:
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(fn, items))


def load_frozen(path: Path, split: Optional[str], limit: Optional[int]) -> List[Dict[str, Any]]:
    signals = json.loads(Path(path).read_text(encoding="utf-8"))
    if split:
        gold = json.loads((Path(path).parent / f"{split}_gold_annotated_v4.json").read_text(encoding="utf-8"))
        keep = {r["signal_id"] for r in gold["records"]}
        signals = [s for s in signals if f"{s['source']}:{s['id']}" in keep]
    return signals[:limit] if limit else signals


def build_workflow(
    relevance_agent: Any,
    risk_agent: Any,
    synthesis_agent: Any,
    collect_live: Optional[Callable[[int], List[Dict[str, Any]]]] = None,
) -> Workflow:
    # ------------------------------------------------------------------ steps
    def load_signals(step_input: StepInput, run_context: RunContext) -> StepOutput:
        opts = _opts(step_input)
        if opts.get("frozen_path"):
            raw = load_frozen(Path(opts["frozen_path"]), opts.get("split"), opts.get("max_signals"))
        else:
            if collect_live is None:
                raise ValueError("No live collector configured")
            raw = collect_live(opts.get("limit_per_source", 5))
        run_context.session_state["raw_signals"] = raw
        return StepOutput(content=f"{len(raw)} raw signals")

    def normalize(step_input: StepInput, run_context: RunContext) -> StepOutput:
        state = run_context.session_state
        collector = SignalCollector()
        state["signals"] = collector.collect(state["raw_signals"])
        return StepOutput(content=collector.summarize_collection(state["signals"]))

    def profile_and_triage(step_input: StepInput, run_context: RunContext) -> StepOutput:
        state = run_context.session_state
        llm_ids, fast_ids = [], []
        for s in state["signals"]:
            (llm_ids if needs_llm_risk(s, profile_signal(s)) else fast_ids).append(f"{s['source']}:{s['id']}")
        state["triage"] = {"risk_llm": llm_ids, "risk_fast_path": fast_ids}
        return StepOutput(content=f"risk LLM: {len(llm_ids)} | fast path: {len(fast_ids)}")

    def _subset(state: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
        wanted = set(state["triage"][key])
        return [s for s in state["signals"] if f"{s['source']}:{s['id']}" in wanted]

    def score_relevance(step_input: StepInput, run_context: RunContext) -> StepOutput:
        state = run_context.session_state
        started = time.perf_counter()
        results = _parallel_map(relevance_agent.score, state["signals"], _opts(step_input).get("concurrency", 4))
        state["relevance"] = {f"{s['source']}:{s['id']}": r for s, r in zip(state["signals"], results)}
        state.setdefault("timings_s", {})["relevance"] = round(time.perf_counter() - started, 2)
        return StepOutput(content=f"relevance scored for {len(results)} signals")

    def assess_risk_llm(step_input: StepInput, run_context: RunContext) -> StepOutput:
        state = run_context.session_state
        subset = _subset(state, "risk_llm")
        started = time.perf_counter()
        results = _parallel_map(risk_agent.assess, subset, _opts(step_input).get("concurrency", 4))
        state["risk_llm"] = {f"{s['source']}:{s['id']}": r for s, r in zip(subset, results)}
        state.setdefault("timings_s", {})["risk_llm"] = round(time.perf_counter() - started, 2)
        return StepOutput(content=f"LLM risk analysis for {len(subset)} signals")

    def assess_risk_fast_path(step_input: StepInput, run_context: RunContext) -> StepOutput:
        state = run_context.session_state
        subset = _subset(state, "risk_fast_path")
        state["risk_fast"] = {f"{s['source']}:{s['id']}": fast_path_risk(s) for s in subset}
        return StepOutput(content=f"deterministic risk for {len(subset)} signals")

    def merge_assessments(step_input: StepInput, run_context: RunContext) -> StepOutput:
        state = run_context.session_state
        risk = {**state.get("risk_fast", {}), **state.get("risk_llm", {})}
        state["assessed"] = [
            {**s, "relevance": state["relevance"][key], "risk": risk[key]}
            for s in state["signals"]
            for key in [f"{s['source']}:{s['id']}"]
        ]
        fallbacks = sum(bool(s["relevance"].get("used_fallback")) + bool(s["risk"].get("used_fallback"))
                        for s in state["assessed"])
        state["fallbacks"] = fallbacks
        return StepOutput(content=f"{len(state['assessed'])} signals assessed, {fallbacks} fallback(s)")

    def llm_synthesis(step_input: StepInput, run_context: RunContext) -> StepOutput:
        synthesis_agent.use_llm = True
        run_context.session_state["digest"] = synthesis_agent.synthesize(run_context.session_state["assessed"])
        return StepOutput(content=run_context.session_state["digest"])

    def deterministic_synthesis(step_input: StepInput, run_context: RunContext) -> StepOutput:
        synthesis_agent.use_llm = False
        run_context.session_state["digest"] = synthesis_agent.synthesize(run_context.session_state["assessed"])
        return StepOutput(content=run_context.session_state["digest"])

    def empty_digest(step_input: StepInput, run_context: RunContext) -> StepOutput:
        run_context.session_state["digest"] = {"total_signals": 0, "executive_summary": "No signals collected.",
                                               "priority_signals": [], "key_signals": [], "recommendations": [],
                                               "synthesis": {"mode": "empty"}}
        return StepOutput(content=run_context.session_state["digest"])

    # ------------------------------------------------------------------ graph
    llm_step = Step(name="llm_synthesis", executor=llm_synthesis,
                    description="LLM-written digest, verified against computed facts and signal ids")
    det_step = Step(name="deterministic_synthesis", executor=deterministic_synthesis,
                    description="Python-only digest (no API key or LLM synthesis disabled)")

    def choose_synthesis(step_input: StepInput) -> List[Step]:
        return [llm_step] if _opts(step_input).get("llm_synthesis", True) else [det_step]

    def has_signals(step_input: StepInput) -> bool:
        return "0 signals assessed" not in str(step_input.previous_step_content or "")

    return Workflow(
        name="SignalGuard v2",
        description="Collect, profile, triage, assess and synthesize technical signals",
        steps=[
            Step(name="load_signals", executor=load_signals),
            Step(name="normalize", executor=normalize),
            Step(name="profile_and_triage", executor=profile_and_triage),
            Parallel(
                Step(name="score_relevance", executor=score_relevance),
                Step(name="assess_risk_llm", executor=assess_risk_llm),
                Step(name="assess_risk_fast_path", executor=assess_risk_fast_path),
                name="analysis",
            ),
            Step(name="merge_assessments", executor=merge_assessments),
            Condition(
                name="has_signals",
                evaluator=has_signals,
                steps=[Router(name="synthesis_router", selector=choose_synthesis, choices=[llm_step, det_step])],
                else_steps=[Step(name="empty_digest", executor=empty_digest)],
            ),
        ],
        telemetry=False,
    )


def run_workflow(workflow: Workflow, **options: Any) -> Dict[str, Any]:
    """Run the workflow and return the final session state (digest, triage, timings...)."""
    state: Dict[str, Any] = {}
    output = workflow.run(input="run signalguard pipeline", additional_data=options, session_state=state)
    if output.content is None or not isinstance(output.content, dict):
        raise RuntimeError(f"Workflow did not produce a digest: {output.content!r}")
    final_state = state if state.get("digest") else {}
    final_state.setdefault("digest", output.content)
    return final_state
