#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/venv/bin/python"

print_header() {
  echo ""
  echo "== $1 =="
}

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: Python virtual environment not found at $PYTHON_BIN"
  echo "Create it first: python3.11 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

print_header "1) Secret hygiene check (.env.example)"
if grep -Eq '(^|[^A-Za-z0-9])(gsk_[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,})' "$ROOT_DIR/.env.example"; then
  echo "Error: Potential real secret detected in .env.example"
  exit 1
fi
echo "OK: No obvious secrets found in .env.example"

print_header "2) Backend import smoke check"
cd "$ROOT_DIR"
"$PYTHON_BIN" -c 'from src.main import app; print("OK: FastAPI app import successful")'

print_header "3) Backend test suite"
"$PYTHON_BIN" -m pytest

print_header "4) Frontend build"
cd "$ROOT_DIR/frontend"
npm run build

print_header "All pre-deploy checks passed"
