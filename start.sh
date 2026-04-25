#!/bin/bash
set -e

echo ""
echo "  ✦ CV Updater"
echo "  ──────────────────────────────"

# Detect local IP for sharing with wife
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "unknown")

cd "$(dirname "$0")/backend"

# Create venv on first run
if [ ! -d "venv" ]; then
  echo "  📦 Setting up Python environment (first run only)..."
  python3 -m venv venv
fi

source venv/bin/activate

# Install / update dependencies quietly
pip install -r requirements.txt -q

# Install Playwright browser on first run
if [ ! -d "$HOME/.cache/ms-playwright" ] && [ ! -d "$HOME/Library/Caches/ms-playwright" ]; then
  echo "  🌐 Installing headless browser for JS rendering (first run only)..."
  python -m playwright install chromium --quiet 2>/dev/null || playwright install chromium
fi

echo ""
echo "  ✅ Server is running!"
echo ""
echo "  Open in browser:"
echo "    This Mac:       http://localhost:8080"
if [ "$LOCAL_IP" != "unknown" ]; then
  echo "    Wife's device:  http://$LOCAL_IP:8080"
fi
echo ""
echo "  Press Ctrl+C to stop."
echo "  ──────────────────────────────"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8080
