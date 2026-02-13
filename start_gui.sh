#!/bin/bash
set -euo pipefail
trap 'kill 0' EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8088
PYTHON_BIN="python3.12"

cd "$SCRIPT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "ERROR: $PYTHON_BIN not found. xatra_gui requires Python >= 3.12 because xatra requires it."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment with $PYTHON_BIN..."
    uv venv --python "$PYTHON_BIN"
fi

source .venv/bin/activate

if ! python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "ERROR: Existing .venv uses $(python -V 2>&1), but xatra requires Python >= 3.12."
    echo "Recreate it with: rm -rf .venv && uv venv --python $PYTHON_BIN"
    exit 1
fi

echo "Installing backend dependencies..."
# uv pip install -r requirements.txt
uv sync

# Prefer a sibling local xatra checkout for development; otherwise use installed package from requirements.
if [ -f "../xatra.master/pyproject.toml" ]; then
    echo "Installing local xatra from ../xatra.master (editable)..."
    uv add --editable ../xatra.master
elif [ -f "../xatra/pyproject.toml" ]; then
    echo "Installing local xatra from ../xatra (editable)..."
    uv add --editable ../xatra
fi

# Free the backend port if something is still running from a previous session
free_port() {
    if command -v fuser >/dev/null 2>&1; then
        fuser -k "$BACKEND_PORT"/tcp 2>/dev/null || true
    fi
    if command -v lsof >/dev/null 2>&1; then
        for pid in $(lsof -ti:"$BACKEND_PORT" 2>/dev/null); do
            kill -9 "$pid" 2>/dev/null || true
        done
    fi
}

port_in_use() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti:"$BACKEND_PORT" >/dev/null 2>&1
    else
        fuser "$BACKEND_PORT"/tcp >/dev/null 2>&1
    fi
}

if port_in_use; then
    echo "Freeing port $BACKEND_PORT (killing existing process(es))..."
    free_port
    for i in 1 2 3 4 5; do
        sleep 1
        if ! port_in_use; then
            break
        fi
        if [ "$i" -eq 5 ]; then
            echo "ERROR: Port $BACKEND_PORT still in use. Try: kill -9 \$(lsof -ti:$BACKEND_PORT)"
            exit 1
        fi
        free_port
    done
fi

echo "Starting Backend (port $BACKEND_PORT)..."
python -m uvicorn main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" &

echo "Starting Frontend..."
cd "$SCRIPT_DIR/frontend"
if [ ! -d node_modules ]; then
    npm install
fi
npm run dev &

wait
