#!/usr/bin/env bash
set -euo pipefail

# Install agentctl using uv
# Requires uv to be installed: https://docs.astral.sh/uv/

if ! command -v uv &> /dev/null; then
  echo "Error: uv is not installed."
  echo "Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

echo "Installing agentctl with uv..."
uv tool install git+https://github.com/ConnorOLone/agentctl.git

echo "✓ agentctl installed successfully"
echo "Run 'agentctl --version' to verify installation"
