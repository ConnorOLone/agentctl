"""Low-level git helpers. Every function takes an explicit *cwd* so callers
never have to ``os.chdir``."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from agentctl.model import Worktree


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def run_git(
    *args: str,
    cwd: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the completed process."""
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=check,
            cwd=cwd,
        )
    except FileNotFoundError:
        print("Error: git is not installed or not on PATH.", file=sys.stderr)
        raise SystemExit(1)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip()
        if stderr:
            print(f"git error: {stderr}", file=sys.stderr)
        raise


# ---------------------------------------------------------------------------
# repo discovery
# ---------------------------------------------------------------------------

def get_repo_root() -> str:
    """Return the repo root for the current working directory."""
    result = run_git("rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        print("Error: not inside a git repository.", file=sys.stderr)
        raise SystemExit(1)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# worktree operations
# ---------------------------------------------------------------------------

def worktree_prune(cwd: str) -> None:
    run_git("worktree", "prune", cwd=cwd)


def worktree_add(path: str, branch: str, base: str, cwd: str) -> None:
    run_git("worktree", "add", "-b", branch, path, base, cwd=cwd)


def worktree_remove(path: str, cwd: str) -> None:
    run_git("worktree", "remove", "--force", path, cwd=cwd)


def worktree_list_human(cwd: str) -> str:
    """Return the human-readable ``git worktree list`` output."""
    return run_git("worktree", "list", cwd=cwd).stdout.strip()


def worktree_list_porcelain(cwd: str) -> list[Worktree]:
    """Parse ``git worktree list --porcelain`` into structured data."""
    result = run_git("worktree", "list", "--porcelain", cwd=cwd)
    worktrees: list[Worktree] = []
    current: dict[str, str | bool] = {}

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(_dict_to_worktree(current))
            current = {"path": line.split(" ", 1)[1]}
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            # refs/heads/agent/task-1 -> agent/task-1
            current["branch"] = line.split(" ", 1)[1].removeprefix("refs/heads/")
        elif line == "bare":
            current["bare"] = True

    if current:
        worktrees.append(_dict_to_worktree(current))

    return worktrees


def _dict_to_worktree(d: dict) -> Worktree:
    return Worktree(
        path=str(d.get("path", "")),
        branch=d.get("branch"),  # type: ignore[arg-type]
        head=d.get("head"),  # type: ignore[arg-type]
        bare=bool(d.get("bare", False)),
    )


# ---------------------------------------------------------------------------
# fetch / branch helpers
# ---------------------------------------------------------------------------

def fetch_origin(cwd: str) -> None:
    run_git("fetch", "origin", "--prune", cwd=cwd)


def resolve_base_ref(cwd: str, base: str | None = None) -> str:
    """Determine the base ref for new worktrees.

    Priority: explicit ``--base`` > ``origin/HEAD`` > ``origin/main``.
    """
    if base:
        return base

    result = run_git(
        "symbolic-ref", "-q", "refs/remotes/origin/HEAD",
        cwd=cwd, check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().removeprefix("refs/remotes/")

    return "origin/main"


def branch_exists(branch: str, cwd: str) -> bool:
    result = run_git(
        "show-ref", "--verify", "--quiet", f"refs/heads/{branch}",
        cwd=cwd, check=False,
    )
    return result.returncode == 0
