from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class JudgeReport:
    hard_flags: List[str] = field(default_factory=list)
    pass_: bool = False
    rewrite_required: bool = False
    scores: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    revision_instructions: List[str] = field(default_factory=list)
    one_sentence_verdict: str = ""


@dataclass
class SessionState:
    """Stateful artifact for one story generation session."""

    # identity
    id: str
    trace_id: str
    created_at: float

    # user input
    user_request_raw: str

    # state machine
    state: str = "INIT"
    transitions: List[Dict[str, Any]] = field(default_factory=list)

    # working memory artifacts
    request_spec: str = ""
    plan: str = ""
    drafts: List[str] = field(default_factory=list)
    judge_reports: List[JudgeReport] = field(default_factory=list)
    final_story: str = ""

    # optional HITL feedback
    user_feedback: str = ""

    # metrics snapshot (from observability)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def new(user_request_raw: str) -> "SessionState":
        now = time.time()
        return SessionState(
            id=f"session_{uuid.uuid4().hex[:12]}",
            trace_id="",
            created_at=now,
            user_request_raw=user_request_raw,
            state="INIT",
            transitions=[{"ts": now, "from": None, "to": "INIT", "reason": "created"}],
        )

    def transition(self, to_state: str, reason: str = "") -> None:
        ts = time.time()
        self.transitions.append(
            {"ts": ts, "from": self.state, "to": to_state, "reason": reason}
        )
        self.state = to_state

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # dataclass JudgeReport → dict already handled by asdict
        return d

    def save(self, sessions_dir: str = "story_studio/sessions") -> str:
        os.makedirs(sessions_dir, exist_ok=True)
        path = os.path.join(sessions_dir, f"{self.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path
