"""agentctl CLI — Git worktree bootstrapper for agentic workflows."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer

from agentctl import __version__
from agentctl.git import (
    branch_exists,
    fetch_origin,
    get_repo_root,
    resolve_base_ref,
    worktree_add,
    worktree_list_human,
    worktree_list_porcelain,
    worktree_prune,
    worktree_remove,
)

app = typer.Typer(
    name="agentctl",
    help="Git worktree bootstrapper for agentic workflows.",
    add_completion=False,
)

# Commands that mutate repo topology — denied in agent mode.
_USER_ONLY = {"init", "rm", "clean"}


def _check_agent_mode(command: str) -> None:
    """Exit non-zero if AGENTCTL_MODE=agent and *command* is user-only."""
    mode = os.environ.get("AGENTCTL_MODE", "").lower()
    if mode == "agent" and command in _USER_ONLY:
        print(
            f"Denied: '{command}' is user-only (AGENTCTL_MODE=agent).",
            file=sys.stderr,
        )
        raise SystemExit(1)


# ---- version callback -----------------------------------------------------
def _version_callback(value: bool) -> None:
    if value:
        print(f"agentctl {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """agentctl — Git worktree bootstrapper for agentic workflows."""


# ---- init ------------------------------------------------------------------

@app.command()
def init(
    count: int = typer.Option(
        2, "--count", "-n", help="Number of worktrees to create."
    ),
    prefix: str = typer.Option(
        "agent", "--prefix", "-p", help="Branch prefix."
    ),
    workdir: str = typer.Option(
        "worktrees", "--workdir", "-w",
        help="Directory for worktrees (relative to repo root).",
    ),
    base: Optional[str] = typer.Option(
        None, "--base", "-b",
        help="Base ref (e.g. origin/main). Auto-detected if omitted.",
    ),
) -> None:
    """Initialize worktrees for agentic tasks."""
    _check_agent_mode("init")

    root = get_repo_root()
    root_path = Path(root)

    if count < 1:
        print("Error: --count must be >= 1.", file=sys.stderr)
        raise SystemExit(1)

    base_ref = resolve_base_ref(root, base)
    wt_dir = root_path / workdir

    print(f"Repo root:    {root}")
    print(f"Worktrees:    {workdir}")
    print(f"Prefix:       {prefix}")
    print(f"Base ref:     {base_ref}")
    print()

    wt_dir.mkdir(parents=True, exist_ok=True)

    print("Pruning stale worktrees...")
    worktree_prune(root)

    print("Fetching origin...")
    fetch_origin(root)

    print("Creating worktrees...")
    created = 0
    for i in range(1, count + 1):
        name = f"task-{i}"
        branch = f"{prefix}/{name}"
        rel_path = f"{workdir}/{name}"
        abs_path = root_path / rel_path

        if abs_path.exists():
            print(f"  Skip: {rel_path} (already exists)")
            continue

        if branch_exists(branch, root):
            print(
                f"Error: branch '{branch}' already exists. "
                "Delete it or choose a different prefix.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        print(f"  + {rel_path}  (branch {branch})")
        worktree_add(rel_path, branch, base_ref, root)
        created += 1

    print(f"\nCreated {created} worktree(s).\n")
    print(worktree_list_human(root))


# ---- list ------------------------------------------------------------------

@app.command("list")
def list_cmd(
    json_output: bool = typer.Option(
        False, "--json", help="Output as structured JSON."
    ),
) -> None:
    """List all worktrees."""
    root = get_repo_root()

    if json_output:
        worktrees = worktree_list_porcelain(root)
        data = {
            "repo_root": root,
            "worktrees": [
                {
                    "path": wt.path,
                    "branch": wt.branch,
                    **({"head_commit": wt.head} if wt.head else {}),
                }
                for wt in worktrees
            ],
        }
        print(json.dumps(data, indent=2))
    else:
        print(worktree_list_human(root))


# ---- clean -----------------------------------------------------------------

@app.command()
def clean() -> None:
    """Prune stale worktree references."""
    _check_agent_mode("clean")

    root = get_repo_root()
    worktree_prune(root)
    print("Pruned. Current worktrees:\n")
    print(worktree_list_human(root))


# ---- rm --------------------------------------------------------------------

@app.command()
def rm(
    name: str = typer.Argument(help="Worktree name (e.g. task-2) or path."),
    workdir: str = typer.Option(
        "worktrees", "--workdir", "-w",
        help="Worktrees directory (used to resolve short names).",
    ),
) -> None:
    """Remove a worktree."""
    _check_agent_mode("rm")

    root = get_repo_root()
    root_path = Path(root)

    # Slash or leading dot → treat as explicit path; otherwise resolve under workdir
    if "/" in name or name.startswith("."):
        rel_path = name
    else:
        rel_path = f"{workdir}/{name}"

    abs_path = root_path / rel_path
    if not abs_path.exists():
        print(f"Error: no such worktree directory: {rel_path}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Removing worktree: {rel_path}")
    worktree_remove(rel_path, root)

    print("Pruning...")
    worktree_prune(root)

    print("\nCurrent worktrees:")
    print(worktree_list_human(root))
