"""GitHub CLI (gh) operations."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from agentctl.model import PRComment


def run_gh(
    *args: str,
    cwd: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a gh CLI command and return the completed process."""
    try:
        return subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=check,
            cwd=cwd,
        )
    except FileNotFoundError:
        print(
            "Error: gh CLI is not installed.\n"
            "Install it from: https://cli.github.com/",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip()
        if stderr:
            print(f"gh error: {stderr}", file=sys.stderr)
        raise


def check_gh_installed() -> bool:
    """Check if gh CLI is installed."""
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_gh_auth(cwd: str | None = None) -> tuple[bool, str]:
    """Check if gh is authenticated.

    Returns:
        (is_authenticated, message)
    """
    result = run_gh("auth", "status", cwd=cwd, check=False)
    authenticated = result.returncode == 0
    message = result.stderr.strip() if result.stderr else result.stdout.strip()
    return authenticated, message


def get_pr_for_branch(branch: str, cwd: str | None = None) -> int | None:
    """Get PR number for the given branch, or None if not found."""
    result = run_gh(
        "pr", "view", branch,
        "--json", "number",
        "--jq", ".number",
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        return None

    try:
        return int(result.stdout.strip())
    except (ValueError, AttributeError):
        return None


def get_pr_comments(pr_number: int, cwd: str | None = None) -> list[PRComment]:
    """Fetch all comments and review comments for a PR.

    Normalizes both issue comments and review comments into a single list.
    """
    # Fetch issue comments
    issue_result = run_gh(
        "api",
        f"repos/{{owner}}/{{repo}}/issues/{pr_number}/comments",
        "--jq",
        '.[] | {author: .user.login, createdAt: .created_at, body: .body, url: .html_url, type: "comment"}',
        cwd=cwd,
        check=False,
    )

    # Fetch review comments
    review_result = run_gh(
        "api",
        f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments",
        "--jq",
        '.[] | {author: .user.login, createdAt: .created_at, body: .body, path: .path, line: .line, url: .html_url, type: "review_comment"}',
        cwd=cwd,
        check=False,
    )

    comments: list[PRComment] = []

    # Parse issue comments
    if issue_result.returncode == 0 and issue_result.stdout.strip():
        for line in issue_result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    data = json.loads(line)
                    comments.append(_dict_to_pr_comment(data))
                except json.JSONDecodeError:
                    continue

    # Parse review comments
    if review_result.returncode == 0 and review_result.stdout.strip():
        for line in review_result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    data = json.loads(line)
                    comments.append(_dict_to_pr_comment(data))
                except json.JSONDecodeError:
                    continue

    # Sort by creation time
    comments.sort(key=lambda c: c.created_at)

    return comments


def _dict_to_pr_comment(data: dict[str, Any]) -> PRComment:
    return PRComment(
        author=data.get("author", "unknown"),
        created_at=data.get("createdAt", ""),
        body=data.get("body", ""),
        path=data.get("path"),
        line=data.get("line"),
        url=data.get("url"),
        comment_type=data.get("type", "comment"),
    )
