# agentctl

A small CLI to bootstrap parallel Git worktrees for "agentic" development workflows.

## Install

### One-liner (recommended)
```bash
curl -fsSL https://raw.githubusercontent.com/<YOUR_GH_USER>/agentctl/main/install.sh | bash
```

### Manual Installation

1. Clone this repository
2. Make the script executable:
   ```bash
   chmod +x agentctl
   ```
3. Optionally, add it to your PATH:
   ```bash
   sudo ln -s "$(pwd)/agentctl" /usr/local/bin/agentctl
   ```

## Usage

### Initialize worktrees

Create multiple worktrees for parallel work:

```bash
agentctl init [--count N] [--prefix agent] [--workdir worktrees] [--base origin/main]
```

Options:
- `--count N`: Number of worktrees to create (default: 2)
- `--prefix`: Branch name prefix (default: "agent")
- `--workdir`: Directory for worktrees (default: "worktrees")
- `--base`: Base branch reference (default: origin/main or origin/HEAD)

Example:
```bash
agentctl init --count 3
```

This creates:
- `worktrees/task-1` with branch `agent/task-1`
- `worktrees/task-2` with branch `agent/task-2`
- `worktrees/task-3` with branch `agent/task-3`

### List worktrees

```bash
agentctl list
```

### Remove a worktree

```bash
agentctl rm <name>
```

Example:
```bash
agentctl rm task-2
```

### Clean stale worktrees

```bash
agentctl clean
```

## Why Worktrees?

Git worktrees allow you to have multiple working directories checked out from the same repository simultaneously. This is useful for:

- Working on multiple features in parallel
- Quickly testing different branches without stashing
- Running CI/CD checks on one branch while developing on another
- Code review without disrupting your current work

## License

MIT License - see [LICENSE](LICENSE) file for details.
