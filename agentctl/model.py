from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Worktree:
    """Represents a single git worktree entry."""

    path: str
    branch: str | None = None
    head: str | None = None
    bare: bool = False
