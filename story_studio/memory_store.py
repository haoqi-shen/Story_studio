from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PreferenceMemory:
    """Minimal, opt-in preference memory.

    We only store lightweight *style* preferences the user explicitly states (HITL),
    not inferred private attributes.
    """

    preferred_length: Optional[str] = None  # short / medium / long
    preferred_tone: Optional[str] = None    # calmer / funnier / etc.
    recurring_character: Optional[str] = None

    def to_text(self) -> str:
        parts = []
        if self.preferred_length:
            parts.append(f"preferred_length={self.preferred_length}")
        if self.preferred_tone:
            parts.append(f"preferred_tone={self.preferred_tone}")
        if self.recurring_character:
            parts.append(f"recurring_character={self.recurring_character}")
        return ", ".join(parts) if parts else "(none)"


class MemoryStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> PreferenceMemory:
        if not self.path.exists():
            return PreferenceMemory()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return PreferenceMemory(**data)

    def save(self, mem: PreferenceMemory) -> None:
        self.path.write_text(json.dumps(mem.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
