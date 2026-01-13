from __future__ import annotations

import json
import re
import time
import uuid
from typing import Callable, Tuple

from story_studio.memory_store import MemoryStore, PreferenceMemory
from story_studio.observability import Logger, Metrics, TraceContext, record_span
from story_studio.prompts import (
    interpreter_prompt,
    planner_prompt,
    storyteller_prompt,
    judge_prompt,
    reviser_prompt,
)
from story_studio.session import SessionState, JudgeReport

ModelFn = Callable[[str, int, float], str]


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction from model output."""
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}


def _is_number(x) -> bool:
    try:
        float(x)
        return True
    except Exception:
        return False


def _to_judge_report(obj: dict) -> JudgeReport:
    return JudgeReport(
        hard_flags=list(obj.get("hard_flags", []) or []),
        pass_=bool(obj.get("pass", False)),
        rewrite_required=bool(obj.get("rewrite_required", False)),
        scores={k: float(v) for k, v in (obj.get("scores", {}) or {}).items() if _is_number(v)},
        issues=list(obj.get("issues", []) or []),
        revision_instructions=list(obj.get("revision_instructions", []) or []),
        one_sentence_verdict=str(obj.get("one_sentence_verdict", "")),
    )


def _hitl_collect_feedback() -> str | None:
    print("\nOptional: leave feedback to refine the story (press Enter to skip).")
    print("Examples: 'shorter', 'calmer', 'more funny', 'use a recurring character named Luna'\n")
    fb = input("Your feedback: ").strip()
    return fb if fb else None


def _hitl_update_memory(mem: PreferenceMemory, feedback: str) -> PreferenceMemory:
    fb = feedback.lower()

    # conservative: only explicit style prefs
    if "short" in fb:
        mem.preferred_length = "short"
    elif "long" in fb:
        mem.preferred_length = "long"
    elif "medium" in fb:
        mem.preferred_length = "medium"

    if "calm" in fb or "cozy" in fb:
        mem.preferred_tone = "calmer"
    elif "funny" in fb or "humor" in fb:
        mem.preferred_tone = "funnier"

    m = re.search(r"named\s+([A-Za-z]{2,20})", feedback)
    if m:
        mem.recurring_character = m.group(1)

    return mem


def run_story_session(
    user_request: str,
    model_fn: ModelFn,
    enable_hitl: bool = True,
    max_iters: int = 2,
    base_temperature: float = 0.4,
    verbose: bool = True,
    debug: bool = False,
    printer=print,
) -> Tuple[str, str]:
    """End-to-end session controller.

    Returns: (final_story, session_artifact_path)
    """

    def _say(msg: str) -> None:
        """Terminal progress output (kept short; avoids dumping full prompts)."""
        if not verbose:
            return
        try:
            printer(msg, flush=True)
        except TypeError:
            printer(msg)

    session = SessionState.new(user_request)
    session.trace_id = str(uuid.uuid4())

    _say(f"[Session] id={session.id} trace_id={session.trace_id}")
    _say(f"[User] {user_request.strip()}")

    logger = Logger(logs_dir="story_studio/logs")
    metrics = Metrics()
    trace = TraceContext(trace_id=session.trace_id)

    mem_store = MemoryStore("story_studio/memory/user_prefs.json")
    memory = mem_store.load()

    # 1) Interpreter
    session.transition("INTERPRETING")
    _say("[1/6] Interpreting request (intent + constraints)...")
    prompt = interpreter_prompt(user_request=user_request, memory_pref=memory.to_text())
    span = trace.child_span("interpreter")
    t0 = time.time()
    spec = model_fn(prompt, 800, 0.2)
    _say(f"      ✓ done ({time.time()-t0:.1f}s)")
    span.close(spec)
    record_span(logger, metrics, span, prompt, spec)
    session.request_spec = spec
    session.transition("INTERPRETED")

    if debug:
        _say("      · request_spec (truncated):")
        _say("      " + (spec.strip().replace("\n", " ")[:180] + ("..." if len(spec) > 180 else "")))

    # 2) Planner
    session.transition("PLANNING")
    _say("[2/6] Planning story outline...")
    prompt = planner_prompt(request_spec=spec)
    span = trace.child_span("planner")
    t0 = time.time()
    plan = model_fn(prompt, 700, 0.2)
    _say(f"      ✓ done ({time.time()-t0:.1f}s)")
    span.close(plan)
    record_span(logger, metrics, span, prompt, plan)
    session.plan = plan
    session.transition("PLANNED")

    if debug:
        _say("      · plan (truncated):")
        _say("      " + (plan.strip().replace("\n", " ")[:180] + ("..." if len(plan) > 180 else "")))

    # 3) Draft + judge + revise loop
    story = ""
    for i in range(max_iters + 1):
        session.transition("DRAFTING")
        _say(f"[3/6] Drafting story (v{i+1})...")
        prompt = storyteller_prompt(request_spec=spec, plan=plan)
        span = trace.child_span("storyteller")
        t0 = time.time()
        story = model_fn(prompt, 2200, base_temperature)
        _say(f"      ✓ done ({time.time()-t0:.1f}s)")
        span.close(story, meta={"iteration": i})
        record_span(logger, metrics, span, prompt, story)
        session.drafts.append(story)
        session.transition("DRAFTED")

        session.transition("JUDGING")
        _say("[4/6] Judging quality & safety...")
        prompt = judge_prompt(request_spec=spec, story=story)
        span = trace.child_span("judge")
        t0 = time.time()
        j_raw = model_fn(prompt, 800, 0.0)
        _say(f"      ✓ done ({time.time()-t0:.1f}s)")
        span.close(j_raw, meta={"iteration": i})
        record_span(logger, metrics, span, prompt, j_raw)

        j_obj = _extract_json(j_raw)
        j_report = _to_judge_report(j_obj)
        session.judge_reports.append(j_report)

        # user-facing judge summary
        cozy = (j_report.scores or {}).get("coziness")
        age_fit = (j_report.scores or {}).get("age_fit")
        _say(
            f"      · pass={j_report.pass_} rewrite_required={j_report.rewrite_required} "
            f"hard_flags={len(j_report.hard_flags)} cozy={cozy} age_fit={age_fit}"
        )
        if debug and j_report.issues:
            _say("      · top issues: " + "; ".join(j_report.issues[:3]))

        # metrics
        metrics.inc("judge.calls", 1)
        if j_report.pass_:
            metrics.inc("judge.pass", 1)
        if j_report.rewrite_required:
            metrics.inc("judge.rewrite_required", 1)
        for k, v in (j_report.scores or {}).items():
            metrics.set_gauge(f"score.{k}", v)

        session.transition("JUDGED")

        if j_report.pass_:
            session.transition("FINALIZED")
            session.final_story = story
            break

        if i == max_iters:
            # best-effort stop
            session.transition("FINALIZED")
            session.final_story = story
            break

        session.transition("REVISING")
        _say("[5/6] Revising story based on judge feedback...")
        if j_report.rewrite_required:
            prompt = storyteller_prompt(request_spec=spec, plan=plan)
            span = trace.child_span("rewrite")
            t0 = time.time()
            story = model_fn(prompt, 2200, 0.2)
            _say(f"      ✓ rewritten ({time.time()-t0:.1f}s)")
            span.close(story, meta={"iteration": i, "mode": "rewrite"})
            record_span(logger, metrics, span, prompt, story)
        else:
            prompt = reviser_prompt(
                request_spec=spec,
                story=story,
                revision_instructions=j_report.revision_instructions,
            )
            span = trace.child_span("reviser")
            t0 = time.time()
            story = model_fn(prompt, 2200, 0.25)
            _say(f"      ✓ revised ({time.time()-t0:.1f}s)")
            span.close(story, meta={"iteration": i, "mode": "revise"})
            record_span(logger, metrics, span, prompt, story)

        session.drafts.append(story)
        session.transition("REVISED")

    # 4) Finalize + show result
    _say("[6/6] Finalizing story...")
    final_story = session.final_story or story
    _say("      ✓ done")

    if verbose:
        _say("\n--- STORY ---")
        printer(final_story)
        _say("--- END STORY ---\n")

    # HITL feedback (optional) — only after the user sees a complete story.
    if enable_hitl:
        fb = _hitl_collect_feedback()
        if fb:
            session.user_feedback = fb

            # 1) update preference memory (opt-in)
            memory = _hitl_update_memory(memory, fb)
            mem_store.save(memory)
            metrics.inc("hitl.feedback", 1)

            # 2) immediately apply feedback to rewrite/revise the story (post-output pass)
            _say("[HITL] Applying your feedback to produce an updated story...")

            hitl_instructions = [
                f"User feedback: {fb}",
                "Apply the feedback while keeping the story safe and age-appropriate (5–10).",
                "Do not add scary elements. Keep a cozy bedtime ending.",
            ]

            prompt = reviser_prompt(
                request_spec=spec,
                story=final_story,
                revision_instructions=hitl_instructions,
            )

            span = trace.child_span("hitl_reviser")
            t0 = time.time()
            updated_story = model_fn(prompt, 2200, 0.35)
            _say(f"      ✓ updated ({time.time()-t0:.1f}s)")
            span.close(updated_story, meta={"mode": "hitl_revise"})
            record_span(logger, metrics, span, prompt, updated_story)

            session.drafts.append(updated_story)
            session.final_story = updated_story
            final_story = updated_story

            _say("\n--- UPDATED STORY (after your feedback) ---")
            printer(final_story)
            _say("--- END UPDATED STORY ---\n")

    # Always persist and return a tuple
    session.metrics = metrics.snapshot()
    session_path = session.save(sessions_dir="story_studio/sessions")
    _say(f"[Saved] {session_path}")

    return final_story, session_path
