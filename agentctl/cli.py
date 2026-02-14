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
    delete_local_branch,
    delete_remote_branch,
    ensure_repo_root_cwd,
    fetch_origin,
    get_current_branch,
    get_repo_root,
    list_branches,
    resolve_base_ref,
    sync_branch,
    worktree_add,
    worktree_list_human,
    worktree_list_porcelain,
    worktree_prune,
    worktree_remove,
)
from agentctl.gh_ops import (
    check_gh_auth,
    check_gh_installed,
    get_pr_comments,
    get_pr_for_branch,
)
from agentctl.model import SyncResult

app = typer.Typer(
    name="agentctl",
    help="Git worktree bootstrapper for agentic workflows.",
    add_completion=False,
)

# Commands that mutate repo topology — denied in agent mode.
# Note: "sync" is NOT in this list because it's an allowed safe mutation for agents.
_USER_ONLY = {"init", "rm", "clean", "reset"}


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

    root = ensure_repo_root_cwd()
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


# ---- sync ------------------------------------------------------------------

@app.command()
def sync(
    base: Optional[str] = typer.Option(
        None, "--base", "-b",
        help="Base ref to sync with (auto-detected if omitted).",
    ),
    strategy: str = typer.Option(
        "rebase", "--strategy", "-s",
        help="Sync strategy: 'rebase' (default) or 'merge'.",
    ),
    autostash: bool = typer.Option(
        False, "--autostash",
        help="Automatically stash/unstash local changes (rebase only).",
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="Output as structured JSON.",
    ),
) -> None:
    """Sync current branch with base (fetch + rebase/merge).

    Keeps long-running agent branches up-to-date. Allowed in agent mode.
    """
    root = ensure_repo_root_cwd()

    if strategy not in ("rebase", "merge"):
        print(
            f"Error: --strategy must be 'rebase' or 'merge', got '{strategy}'",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Fetch first
    if not json_output:
        print("Fetching origin...")
    fetch_origin(root)

    # Determine current branch
    branch = get_current_branch(root)
    if branch is None:
        print("Error: detached HEAD. Check out a branch first.", file=sys.stderr)
        raise SystemExit(1)

    # Resolve base ref
    base_ref = resolve_base_ref(root, base)

    # Perform sync
    if not json_output:
        print(f"Syncing '{branch}' with '{base_ref}' (strategy: {strategy})...")

    success, message, conflicts = sync_branch(
        base_ref,
        strategy=strategy,
        autostash=autostash,
        cwd=root,
    )

    # Determine if anything changed
    # If message contains "Already up to date" or similar, changed=False
    changed = "up to date" not in message.lower() and "up-to-date" not in message.lower()

    result = SyncResult(
        repo_root=root,
        branch=branch,
        base=base_ref,
        strategy=strategy,
        success=success,
        message=message,
        changed=changed,
        conflicts=conflicts,
    )

    if json_output:
        print(
            json.dumps(
                {
                    "repo_root": result.repo_root,
                    "branch": result.branch,
                    "base": result.base,
                    "strategy": result.strategy,
                    "success": result.success,
                    "message": result.message,
                    "changed": result.changed,
                    "conflicts": result.conflicts,
                },
                indent=2,
            )
        )
    else:
        if success:
            status = "✓" if changed else "✓ (already up to date)"
            print(f"{status} Branch '{branch}' synced with '{base_ref}'")
            if message and changed:
                print(f"\n{message}")
        else:
            print(f"✗ Sync failed", file=sys.stderr)
            if message:
                print(f"\n{message}", file=sys.stderr)
            if conflicts:
                print(
                    "\nConflicts detected. Resolve conflicts and continue/abort manually.",
                    file=sys.stderr,
                )
            raise SystemExit(1)


# ---- list ------------------------------------------------------------------

@app.command("list")
def list_cmd(
    json_output: bool = typer.Option(
        False, "--json", help="Output as structured JSON."
    ),
) -> None:
    """List all worktrees."""
    root = ensure_repo_root_cwd()

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

    root = ensure_repo_root_cwd()
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

    root = ensure_repo_root_cwd()
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


# ---- reset -----------------------------------------------------------------

@app.command()
def reset(
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Confirm reset operation (required).",
    ),
    workdir: str = typer.Option(
        "worktrees", "--workdir", "-w",
        help="Worktrees directory to clear.",
    ),
    prefix: str = typer.Option(
        "agent", "--prefix", "-p",
        help="Branch prefix to delete.",
    ),
    delete_remote: bool = typer.Option(
        False, "--delete-remote",
        help="Also delete remote branches.",
    ),
    recreate: bool = typer.Option(
        False, "--recreate",
        help="Recreate worktrees after reset.",
    ),
    count: int = typer.Option(
        2, "--count", "-n",
        help="Number of worktrees to recreate (if --recreate).",
    ),
    base: Optional[str] = typer.Option(
        None, "--base", "-b",
        help="Base ref for recreated worktrees (if --recreate).",
    ),
) -> None:
    """Reset agent worktrees and branches.

    Removes worktrees under workdir, prunes, deletes local (and optionally remote)
    branches matching prefix/task-*, and optionally recreates worktrees.
    """
    _check_agent_mode("reset")

    # Require --yes flag
    if not yes:
        print(
            "Error: --yes flag is required to confirm reset operation.\n"
            "This will remove worktrees and delete branches.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    root = ensure_repo_root_cwd()
    root_path = Path(root)
    wt_dir = root_path / workdir

    print(f"Repo root:       {root}")
    print(f"Worktrees dir:   {workdir}")
    print(f"Branch prefix:   {prefix}")
    print(f"Delete remote:   {delete_remote}")
    print(f"Recreate:        {recreate}")
    if recreate:
        print(f"  Count:         {count}")
        print(f"  Base:          {base or '(auto-detect)'}")
    print()

    # Step 1: Remove worktrees under workdir
    print(f"Removing worktrees under {workdir}...")
    removed_count = 0
    if wt_dir.exists():
        worktrees = worktree_list_porcelain(root)
        for wt in worktrees:
            # Check if worktree is under our workdir
            wt_path = Path(wt.path)
            try:
                wt_path.relative_to(wt_dir)
                # It's under workdir, remove it
                print(f"  - {wt.path}")
                worktree_remove(wt.path, root)
                removed_count += 1
            except ValueError:
                # Not under workdir, skip
                continue
    print(f"Removed {removed_count} worktree(s).")
    print()

    # Step 2: Prune worktrees
    print("Pruning worktree references...")
    worktree_prune(root)
    print()

    # Step 3: Delete local branches matching prefix/task-*
    print(f"Deleting local branches matching '{prefix}/task-*'...")
    branch_pattern = f"{prefix}/task-*"
    local_branches = list_branches(branch_pattern, root)
    deleted_local = 0
    if local_branches:
        for branch in local_branches:
            print(f"  - {branch}")
            if delete_local_branch(branch, root):
                deleted_local += 1
            else:
                print(f"    Warning: failed to delete {branch}", file=sys.stderr)
    print(f"Deleted {deleted_local} local branch(es).")
    print()

    # Step 4: Optionally delete remote branches
    if delete_remote:
        print(f"Deleting remote branches matching '{prefix}/task-*'...")
        # For each local branch we found, try to delete it from origin
        deleted_remote = 0
        if local_branches:
            for branch in local_branches:
                # Extract the branch name without prefix (e.g., "agent/task-1" -> "agent/task-1")
                print(f"  - origin/{branch}")
                if delete_remote_branch(branch, "origin", root):
                    deleted_remote += 1
                else:
                    # Might not exist on remote, that's okay
                    print(f"    (not found or already deleted)")
        print(f"Deleted {deleted_remote} remote branch(es).")
        print()

    # Step 5: Optionally recreate worktrees
    if recreate:
        print("Recreating worktrees...")
        print()

        if count < 1:
            print("Error: --count must be >= 1.", file=sys.stderr)
            raise SystemExit(1)

        base_ref = resolve_base_ref(root, base)
        wt_dir.mkdir(parents=True, exist_ok=True)

        print(f"Base ref:     {base_ref}")
        print()

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
                    "This shouldn't happen after reset.",
                    file=sys.stderr,
                )
                raise SystemExit(1)

            print(f"  + {rel_path}  (branch {branch})")
            worktree_add(rel_path, branch, base_ref, root)
            created += 1

        print(f"\nCreated {created} worktree(s).\n")

    # Final status
    print("Current worktrees:")
    print(worktree_list_human(root))


# ---- pr --------------------------------------------------------------------

pr_app = typer.Typer(
    name="pr",
    help="GitHub Pull Request operations.",
    add_completion=False,
)
app.add_typer(pr_app, name="pr")


@pr_app.command("comments")
def pr_comments(
    pr_number: Optional[int] = typer.Option(
        None, "--pr",
        help="PR number (auto-detected from current branch if omitted).",
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="Output as structured JSON.",
    ),
) -> None:
    """Fetch PR comments (issue + review comments).

    Read-only operation, allowed in agent mode.
    """
    root = ensure_repo_root_cwd()

    # Check gh installation
    if not check_gh_installed():
        print(
            "Error: gh CLI is not installed.\n"
            "Install from: https://cli.github.com/",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Check authentication
    authenticated, auth_msg = check_gh_auth(root)
    if not authenticated:
        print(
            "Error: gh is not authenticated.\n"
            f"{auth_msg}\n\n"
            "Run: gh auth login",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Determine PR number
    if pr_number is None:
        branch = get_current_branch(root)
        if branch is None:
            print(
                "Error: detached HEAD and no --pr specified.\n"
                "Check out a branch or provide --pr <number>.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        pr_number = get_pr_for_branch(branch, root)
        if pr_number is None:
            print(
                f"Error: no PR found for branch '{branch}'.\n"
                "Specify --pr <number> explicitly.",
                file=sys.stderr,
            )
            raise SystemExit(1)

    # Fetch comments
    comments = get_pr_comments(pr_number, root)

    if json_output:
        output = [
            {
                "author": c.author,
                "createdAt": c.created_at,
                "body": c.body,
                "type": c.comment_type,
                **({"path": c.path} if c.path else {}),
                **({"line": c.line} if c.line else {}),
                **({"url": c.url} if c.url else {}),
            }
            for c in comments
        ]
        print(json.dumps(output, indent=2))
    else:
        if not comments:
            print(f"No comments found for PR #{pr_number}.")
        else:
            print(f"Comments for PR #{pr_number}:\n")
            for i, comment in enumerate(comments, 1):
                location = ""
                if comment.path and comment.line:
                    location = f" ({comment.path}:{comment.line})"
                elif comment.path:
                    location = f" ({comment.path})"

                print(f"[{i}] {comment.author}{location} — {comment.created_at}")
                print(f"    {comment.body[:100]}{'...' if len(comment.body) > 100 else ''}")
                if comment.url:
                    print(f"    {comment.url}")
                print()


# ---- doctor ----------------------------------------------------------------

@app.command()
def doctor() -> None:
    """Check system dependencies and configuration.

    Read-only diagnostic tool, allowed in agent mode.
    """
    print("Checking agentctl dependencies...\n")

    # Check git
    try:
        result = get_repo_root()
        print(f"✓ git installed")
        print(f"  Repo root: {result}")
    except SystemExit:
        print("✗ git not found or not in a repository")

    print()

    # Check gh
    if check_gh_installed():
        print("✓ gh CLI installed")
        root = get_repo_root()
        authenticated, msg = check_gh_auth(root)
        if authenticated:
            print("  ✓ Authenticated")
            # Print first line of auth message (usually shows user)
            first_line = msg.split("\n")[0] if msg else ""
            if first_line:
                print(f"  {first_line}")
        else:
            print("  ✗ Not authenticated")
            print("  Run: gh auth login")
    else:
        print("✗ gh CLI not installed")
        print("  Install from: https://cli.github.com/")

    print()
    print("All checks complete.")
