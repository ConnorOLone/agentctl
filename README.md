# agentctl

Git worktree bootstrapper for agentic workflows. Sets up isolated worktrees so
multiple AI agents (or humans) can work in the same repo without stepping on
each other.

## Install

```bash
# recommended — isolated install, available globally
uv tool install .

# or editable dev install
uv pip install -e .
```

After install, `agentctl` is available on your PATH.

## Usage

Run from anywhere inside a git repository. All commands automatically normalize to the repo root, so they work correctly from any subdirectory.

### Initialize worktrees

```bash
agentctl init                          # 2 worktrees, default settings
agentctl init --count 4                # 4 worktrees
agentctl init -n 3 --prefix ai        # branches: ai/task-1 .. ai/task-3
agentctl init --base origin/develop    # branch off develop instead of main
```

Creates `worktrees/task-1 .. task-N` under the repo root, each on a new branch
`<prefix>/task-i` based on the resolved base ref.

### List worktrees

```bash
agentctl list          # human-readable
agentctl list --json   # structured JSON output
```

### Clean stale references

```bash
agentctl clean
```

### Remove a worktree

```bash
agentctl rm task-2                  # resolves to worktrees/task-2
agentctl rm worktrees/task-2        # explicit path
```

### Reset worktrees and branches

Completely reset the agent workspace: remove all worktrees, delete branches, and optionally recreate fresh worktrees.

```bash
agentctl reset --yes                           # remove worktrees & delete local branches
agentctl reset --yes --delete-remote           # also delete remote branches
agentctl reset --yes --recreate                # reset and recreate 2 worktrees
agentctl reset --yes --recreate -n 4           # reset and recreate 4 worktrees
agentctl reset --yes --prefix ai               # reset branches with 'ai' prefix
agentctl reset --yes --recreate --base develop # recreate from develop branch
```

**Behavior:**
- Requires `--yes` flag to prevent accidental resets
- Removes all worktrees under `--workdir` (default: `worktrees`)
- Prunes worktree references
- Deletes all local branches matching `<prefix>/task-*` pattern
- Optionally deletes matching remote branches with `--delete-remote`
- Optionally recreates worktrees with `--recreate` (uses same logic as `init`)

**User-only command** — denied in agent mode.

### Sync branch with base

Keep long-running agent branches up-to-date after other branches merge into main.

```bash
agentctl sync                              # rebase on auto-detected base
agentctl sync --strategy merge             # use merge instead of rebase
agentctl sync --base origin/develop        # explicit base ref
agentctl sync --autostash                  # auto-stash local changes
agentctl sync --json                       # structured output

# Agent usage
AGENTCTL_MODE=agent agentctl sync          # allowed in agent mode
```

**Behavior:**
- Fetches from origin
- Detects current branch (errors on detached HEAD)
- Resolves base ref: `--base` → `origin/HEAD` → `origin/main` → `origin/master` → `main`
- Performs rebase (default) or merge
- Reports success/conflicts in human or JSON format

### View PR comments

Fetch all PR comments (issue + review comments) without manual copy/paste.

```bash
agentctl pr comments                    # auto-detect PR from current branch
agentctl pr comments --pr 123           # explicit PR number
agentctl pr comments --json             # structured output
```

**Requirements:**
- `gh` CLI must be installed and authenticated
- Run `gh auth login` if not authenticated

**Output includes:**
- Author, timestamp, comment body
- File path and line (for review comments)
- Comment URL

### Check system dependencies

```bash
agentctl doctor
```

Validates:
- git installation and repo root
- gh CLI installation and authentication
- Helpful for debugging setup issues

### Version

```bash
agentctl --version
```

## Example workflow

```bash
# User: Set up agent worktrees
agentctl init --count 3

# Agent (in worktree): Stay synced with main
export AGENTCTL_MODE=agent
agentctl sync

# Agent: Check PR feedback
agentctl pr comments

# Agent: Verify setup
agentctl doctor
```

## Agent mode

Set `AGENTCTL_MODE=agent` to restrict the CLI to safe commands. Topology-changing
commands (`init`, `rm`, `clean`, `reset`) are denied, but read-only and safe mutation
commands are allowed.

**Allowed in agent mode:**
- `list` — read worktrees
- `sync` — safe mutation (keeps branches up-to-date)
- `pr comments` — read PR feedback
- `doctor` — diagnostics

**Denied in agent mode:**
- `init` — creates worktrees (topology change)
- `rm` — removes worktrees (topology change)
- `clean` — prunes references (topology change)
- `reset` — removes worktrees and deletes branches (topology change)

```bash
export AGENTCTL_MODE=agent
agentctl list               # allowed
agentctl sync               # allowed (safe mutation)
agentctl pr comments        # allowed (read-only)
agentctl init               # denied: 'init' is user-only
```

## Test plan

Manual smoke tests — run from a git repo with a remote called `origin`.

| # | Test | Command | Expected |
|---|------|---------|----------|
| 1 | Init default | `agentctl init` | Creates `worktrees/task-1`, `worktrees/task-2` |
| 2 | Init custom count | `agentctl init -n 3 --prefix ai` | Creates 3 worktrees with `ai/task-*` branches |
| 3 | Init skip existing | Run init twice | Second run skips already-created worktrees |
| 4 | Init branch collision | Create branch `agent/task-1` manually, then init | Error about existing branch |
| 5 | List human | `agentctl list` | Shows `git worktree list` output |
| 6 | List JSON | `agentctl list --json` | Valid JSON with repo_root and worktrees array |
| 7 | Clean | `agentctl clean` | Prunes and shows list |
| 8 | Remove | `agentctl rm task-1` | Removes worktree, prunes, shows list |
| 9 | Remove missing | `agentctl rm nonexistent` | Clean error message |
| 10 | Agent mode deny | `AGENTCTL_MODE=agent agentctl init` | "Denied: 'init' is user-only" |
| 11 | Agent mode allow | `AGENTCTL_MODE=agent agentctl list` | Works normally |
| 12 | Outside git repo | `cd /tmp && agentctl list` | "not inside a git repository" |
| 13 | Version | `agentctl --version` | Prints `agentctl 0.1.0` |
| 14 | Sync rebase | `agentctl sync` | Fetches and rebases on base |
| 15 | Sync merge | `agentctl sync --strategy merge` | Fetches and merges base |
| 16 | Sync JSON | `agentctl sync --json` | Valid JSON with success/conflicts |
| 17 | Sync agent mode | `AGENTCTL_MODE=agent agentctl sync` | Works (allowed) |
| 18 | Sync detached HEAD | Checkout detached HEAD, run `agentctl sync` | Error: detached HEAD |
| 19 | PR comments auto | In branch with PR, `agentctl pr comments` | Shows comments |
| 20 | PR comments explicit | `agentctl pr comments --pr 123` | Shows comments for PR #123 |
| 21 | PR comments JSON | `agentctl pr comments --json` | Valid JSON array |
| 22 | PR comments no gh | Rename gh binary, `agentctl pr comments` | Error: gh not installed |
| 23 | PR comments no auth | `gh auth logout`, `agentctl pr comments` | Error: not authenticated |
| 24 | Doctor check | `agentctl doctor` | Shows git ✓, gh status, repo root |
| 25 | Subdirectory execution | `cd worktrees/task-1 && agentctl list` | Works (normalizes to repo root) |
| 26 | Reset requires --yes | `agentctl reset` | Error: --yes flag is required |
| 27 | Reset basic | `agentctl init && agentctl reset --yes` | Removes worktrees, deletes local branches, shows empty list |
| 28 | Reset with remote delete | `agentctl reset --yes --delete-remote` | Also deletes branches on origin |
| 29 | Reset and recreate | `agentctl reset --yes --recreate` | Resets then creates 2 fresh worktrees |
| 30 | Reset recreate custom | `agentctl reset --yes --recreate -n 3 --prefix ai` | Resets then creates 3 worktrees with ai/* branches |
| 31 | Reset agent mode deny | `AGENTCTL_MODE=agent agentctl reset --yes` | "Denied: 'reset' is user-only" |

## License

MIT
