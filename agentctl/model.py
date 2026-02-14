from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Worktree:
    """Represents a single git worktree entry."""

    path: str
    branch: str | None = None
    head: str | None = None
    bare: bool = False


@dataclass
class SyncResult:
    """Result of a sync operation."""

    repo_root: str
    branch: str
    base: str
    strategy: str
    success: bool
    message: str
    changed: bool
    conflicts: bool


@dataclass
class PRComment:
    """Represents a PR comment (issue comment or review comment)."""

    author: str
    created_at: str
    body: str
    path: str | None = None
    line: int | None = None
    url: str | None = None
    comment_type: str = "comment"  # "comment" or "review_comment"
