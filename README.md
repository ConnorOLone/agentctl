# agentctl

Git worktree bootstrapper for agentic workflows. Sets up isolated worktrees so
multiple AI agents (or humans) can work in the same repo without stepping on
each other.

## Install

```bash
# recommended — isolated install, available globally
pipx install .

# or editable dev install
pip install -e .
```

After install, `agentctl` is available on your PATH.

## Usage

Run from anywhere inside a git repository.

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

### Version

```bash
agentctl --version
```

## Agent mode

Set `AGENTCTL_MODE=agent` to restrict the CLI to read-only commands. Mutating
commands (`init`, `rm`, `clean`) are denied with a clear error.

```bash
export AGENTCTL_MODE=agent
agentctl list        # allowed
agentctl init        # denied: 'init' is user-only
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

## License

MIT
