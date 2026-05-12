#!/usr/bin/env bash
# run.sh — start the agentic-personal-assistant Gradio app
# Run: bash run.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/.venv"

if [ ! -d "$VENV" ]; then
    echo "Virtual environment not found. Run setup first:"
    echo "  bash setup.sh"
    exit 1
fi

PYTHONPATH="$PROJECT_DIR" "$VENV/bin/python3" "$PROJECT_DIR/main.py"
