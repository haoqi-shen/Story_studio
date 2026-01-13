from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchBackedRubric:
    """Compact research-to-rubric mapping.

    This is intentionally short: it acts as the bridge between (a) a mini literature survey
    and (b) the judge's operational criteria.
    """

    # Hard constraints (gating): must not be violated
    hard_safety: tuple[str, ...] = (
        "No graphic violence, gore, death, self-harm, or sexual content.",
        "No explicit threats, torture, or horror framing.",
        "No hate/harassment; avoid stereotypes; be inclusive.",
        "No medical/legal/financial advice; this is fiction for kids.",
    )

    # Soft quality dimensions (graded)
    quality_dims: tuple[str, ...] = (
        "Age-appropriate language for 5–10 (simple sentences, explain unfamiliar ideas).",
        "Low arousal: calming tone, gentle conflict, de-escalating emotional arc.",
        "Predictable structure: clear beginning-middle-end with closure.",
        "Cozy sensory detail + reassurance; ending includes a wind-down/bedtime ritual.",
        "Intent alignment: honors user's theme while staying safe and bedtime-appropriate.",
        "Cultural sensitivity: interpret ambiguous motifs (e.g., dragons) in a non-threatening, prosocial way.",
    )


RUBRIC = ResearchBackedRubric()


def interpreter_prompt(user_request: str, memory_pref: str | None) -> str:
    pref = memory_pref or "(none)"
    return f"""You are an intent interpreter for a bedtime-story system.

Task: Convert the user's request into a *Story Request Spec*.
The user prompt is underspecified; infer missing constraints for bedtime stories for ages 5–10.

User request:
{user_request}

Known user preferences (optional; safety overrides preferences):
{pref}

Output format:
Story Request Spec:
- Theme:
- Main character(s):
- Setting:
- Tone (must be calming):
- Length target (short/medium/long):
- Must-include (1–3 items):
- Must-avoid (hard safety constraints):
- Notes on cultural interpretation (if applicable):
""".strip()


def planner_prompt(request_spec: str) -> str:
    return f"""You are a story planner for a bedtime story (ages 5–10).
Create a simple, cozy outline with a gentle arc.

Constraints:
- Keep conflict mild and non-scary.
- One clear main thread; no complex twists.
- End with emotional closure and a bedtime wind-down scene.

Request Spec:
{request_spec}

Output as 6–8 bullet points:
1) Hook
2) Character + want
3) Gentle obstacle
4) Helper / coping strategy
5) Progress
6) Resolution
7) Wind-down bedtime moment
""".strip()


def storyteller_prompt(request_spec: str, plan: str) -> str:
    hard = "\n".join(f"- {x}" for x in RUBRIC.hard_safety)
    return f"""You are a bedtime storyteller for children ages 5–10.

Hard safety constraints (must obey):
{hard}

Style constraints:
- Calm, warm, reassuring.
- Simple language; short paragraphs.
- Gentle humor is OK, but keep arousal low.
- Clear beginning-middle-end; end with closure and sleepiness.

Request Spec:
{request_spec}

Plan:
{plan}

Write the full story (about 600–900 words).""".strip()


def judge_prompt(request_spec: str, story: str) -> str:
    hard = "\n".join(f"- {x}" for x in RUBRIC.hard_safety)
    soft = "\n".join(f"- {x}" for x in RUBRIC.quality_dims)
    return f"""You are a conservative evaluator (LLM Judge) for AI-generated bedtime stories for children ages 5–10.

You MUST output a single JSON object. No extra text.

Hard safety constraints (gating):
{hard}

Soft quality dimensions (graded):
{soft}

Task:
1) Identify any hard safety violations.
2) Evaluate the story along the soft dimensions.
3) Decide:
   - pass: true only if no hard violations AND overall quality is suitable for bedtime.
   - rewrite_required: true if there is any hard violation OR the story is too scary/stimulating for bedtime.
4) Provide actionable revision instructions.

Return JSON with this schema:
{{
  "hard_flags": ["..."],
  "pass": true/false,
  "rewrite_required": true/false,
  "scores": {{
    "age_fit": 0-10,
    "coziness": 0-10,
    "low_arousal": 0-10,
    "structure": 0-10,
    "cultural_ethics": 0-10,
    "intent_alignment": 0-10
  }},
  "issues": ["..."],
  "revision_instructions": ["..."],
  "one_sentence_verdict": "..."
}}

Request Spec:
{request_spec}

Story:
{story}
""".strip()


def reviser_prompt(request_spec: str, story: str, revision_instructions: list[str]) -> str:
    instr = "\n".join(f"- {x}" for x in revision_instructions)
    return f"""You are a reviser for a bedtime story for children ages 5–10.

Goal: Produce a safer, calmer, clearer bedtime story.
Rules:
- Do NOT introduce new major plot elements, new villains, or new threats.
- Reduce arousal; soften conflict; increase reassurance.
- Preserve the user's theme and keep the story coherent.

Request Spec:
{request_spec}

Revision instructions:
{instr}

Original story:
{story}

Return the revised full story only.""".strip()
