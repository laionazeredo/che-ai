#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHE_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "--- Che Multi-Agent Setup ---"
echo "Che Repo: $CHE_REPO"
echo

# Detection
HAS_CODEX=0
command -v codex >/dev/null 2>&1 && HAS_CODEX=1

HAS_CLAUDE=0
command -v claude >/dev/null 2>&1 && HAS_CLAUDE=1

HAS_CURSOR=0
(command -v cursor >/dev/null 2>&1 || [ -d "/Applications/Cursor.app" ] || [ -d "$HOME/.cursor" ]) && HAS_CURSOR=1

echo "Detected agents:"
[ $HAS_CODEX -eq 1 ] && echo "  [X] Codex" || echo "  [ ] Codex (not found)"
[ $HAS_CLAUDE -eq 1 ] && echo "  [X] Claude Code" || echo "  [ ] Claude Code (not found)"
[ $HAS_CURSOR -eq 1 ] && echo "  [X] Cursor" || echo "  [ ] Cursor (not found)"
echo "  [X] Trae (Default)"
echo

# Interactive selection if running in a terminal
if [ -t 0 ] || [ -c /dev/tty ]; then
    # Redirect stdin to /dev/tty to allow interactive input even if script is piped
    exec 3<&0
    exec < /dev/tty

    echo "Select adapters to install (comma separated numbers, e.g. 1,2,4):"
    echo "1) Codex"
    echo "2) Claude Code"
    echo "3) Cursor"
    echo "4) Trae (Global rules)"
    echo "5) ALL detected"
    echo "q) Quit"
    read -p "Selection: " choice

    # Restore stdin
    exec <&3
    exec 3<&-

    if [[ "$choice" == "q" ]]; then
        echo "Setup aborted."
        exit 0
    fi

    install_codex=0
    install_claude=0
    install_cursor=0
    install_trae=0

    if [[ "$choice" == "5" ]]; then
        [ $HAS_CODEX -eq 1 ] && install_codex=1
        [ $HAS_CLAUDE -eq 1 ] && install_claude=1
        [ $HAS_CURSOR -eq 1 ] && install_cursor=1
        install_trae=1
    else
        IFS=',' read -ra ADAPTERS <<< "$choice"
        for a in "${ADAPTERS[@]}"; do
            case $a in
                1) install_codex=1 ;;
                2) install_claude=1 ;;
                3) install_cursor=1 ;;
                4) install_trae=1 ;;
            esac
        done
    fi
else
    # Non-interactive mode: install all detected
    echo "Non-interactive mode detected. Installing all available adapters..."
    install_codex=$HAS_CODEX
    install_claude=$HAS_CLAUDE
    install_cursor=$HAS_CURSOR
    install_trae=1
fi

# Execution
if [ $install_codex -eq 1 ]; then
    echo "Installing Codex adapter..."
    "$CHE_REPO/adapters/codex/install.sh"
fi

if [ $install_claude -eq 1 ]; then
    echo "Installing Claude Code adapter..."
    "$CHE_REPO/adapters/claude/install.sh"
fi

if [ $install_cursor -eq 1 ]; then
    echo "Installing Cursor adapter..."
    "$CHE_REPO/adapters/cursor/install.sh"
fi

if [ $install_trae -eq 1 ]; then
    echo "Ensuring Trae global rules..."
    # Trae uses the repo root directly, but we can ensure ~/.trae is current
    # This is mostly a placeholder for future global Trae config
    echo "Trae ready."
fi

echo
echo "--- Setup Complete ---"
