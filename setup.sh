#!/usr/bin/env bash
# setup.sh — one-time project setup for agentic-personal-assistant
# Run: bash setup.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/.venv"

echo "==> Creating virtual environment..."
python3 -m venv "$VENV"

echo "==> Installing dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"
"$VENV/bin/pip" install --quiet gradio  # not in requirements.txt

echo "==> Checking .env..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "    .env created from .env.example — fill in your API keys before running."
fi

echo "==> Checking Google credentials..."
CREDS="$PROJECT_DIR/auth/credentials/client_secret.json"
TOKEN="$PROJECT_DIR/auth/credentials/token.json"

if [ ! -f "$CREDS" ]; then
    echo ""
    echo "    [!] auth/credentials/client_secret.json not found."
    echo "    Download it from Google Cloud Console:"
    echo "      1. console.cloud.google.com → your project"
    echo "      2. APIs & Services → Credentials → OAuth 2.0 Client (Desktop App)"
    echo "      3. Download JSON → rename to client_secret.json"
    echo "      4. Place in: auth/credentials/"
    echo ""
else
    if [ ! -f "$TOKEN" ]; then
        echo "==> Running Google OAuth (browser will open)..."
        PYTHONPATH="$PROJECT_DIR" "$VENV/bin/python3" "$PROJECT_DIR/auth/google_auth.py"
    else
        echo "==> Google token already exists, skipping OAuth."
    fi
fi

echo ""
echo "Setup complete. Start the app with:"
echo "  PYTHONPATH=$PROJECT_DIR $VENV/bin/python3 $PROJECT_DIR/main.py"
echo ""
echo "Or use the run script:"
echo "  bash run.sh"
