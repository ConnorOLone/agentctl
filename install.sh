#!/usr/bin/env bash
set -euo pipefail

REPO_RAW_URL="https://raw.githubusercontent.com/ConnorOLone/agentctl/main/agentctl"
INSTALL_DIR="${INSTALL_DIR:-$HOME/bin}"

mkdir -p "$INSTALL_DIR"
curl -fsSL "$REPO_RAW_URL" -o "$INSTALL_DIR/agentctl"
chmod +x "$INSTALL_DIR/agentctl"

if ! echo "$PATH" | tr ':' '\n' | grep -qx "$INSTALL_DIR"; then
  echo "Installed to $INSTALL_DIR but it is not on PATH."
  echo "Add this to your shell config (e.g. ~/.zshrc):"
  echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
else
  echo "Installed agentctl to $INSTALL_DIR/agentctl"
fi
