# Hippocratic AI Coding Assignment – Bedtime Story Studio

This project implements a **research-informed, multi-agent bedtime story system (ages 5–10)** with an **LLM-as-a-Judge feedback loop**, **session/state/memory**, and **agent quality observability** (logs, traces, metrics).

The goal is not just to generate a story, but to **reliably produce safe, calming, age-appropriate bedtime narratives** in an open-ended setting.

---

## 1. Product framing

Bedtime stories are part of a **sleep routine**, not a neutral creative task.  
This system treats user prompts as **underspecified intent** and applies evidence-informed constraints to ensure:

- low arousal and calming narrative arcs  
- age-appropriate language and cognitive load  
- predictable structure with clear closure  
- ethical and cultural safety by default  

These principles are enforced through a structured judge rubric.

---

## 2. System design

### Multi-agent pipeline

- **Intent Interpreter** → converts the user prompt into a structured *Story Request Spec*  
- **Planner** → generates a gentle story outline  
- **Storyteller** → drafts the story  
- **LLM Judge** → applies a rubric and returns structured JSON (pass/fail, flags, scores, revision instructions)  
- **Reviser / Rewrite** → fixes issues and reduces arousal until the story passes or reaches a safe best-effort output  

### Session, state, and memory (context engineering)

Each run is a **session artifact** saved to `story_studio/sessions/<session_id>.json`, including:
- request spec, plan, drafts, judge reports, and final story  
- explicit state transitions (`INIT → … → FINALIZED`)

Memory is deliberately minimal and controlled:
- **Working memory**: per-session drafts and judge feedback  
- **Opt-in preference memory**: saved only from explicit Human-in-the-Loop feedback (length, tone, recurring character)

---

## 3. Agent quality & observability

Quality assurance is built in via observability:
- **Logs (diary)**: structured events (`story_studio/logs/events.jsonl`)  
- **Traces (narrative)**: per-agent spans (interpreter, planner, judge, etc.)  
- **Metrics (health report)**: latency, judge pass rates, score gauges  

This enables continuous offline evaluation and iterative improvement.

---

## 4. Judge rubric (overview)

The LLM Judge enforces:
- **Hard gates**: violence, threats, horror framing, sexual content, hate, etc.  
- **Soft scores (0–10)**: age fit, coziness, low arousal, structure/closure, ethical & cultural safety, intent alignment  

The judge always returns a single structured JSON object.

---

## 5. How to run

```bash
export OPENAI_API_KEY="..."
python main.py
```

Outputs:
- Session artifacts: `story_studio/sessions/*.json`
- Logs: `story_studio/logs/events.jsonl`
- Preference memory: `story_studio/memory/user_prefs.json`

---

## 6. From prototype to production

Next steps beyond this assignment:
- Offline evaluation sets with slice dashboards (topic, genre, risk)
- Judge calibration with small HITL labels
- Regression tests and red-teaming prompts
- Optional MCP-style tool interface for safe external knowledge retrieval
