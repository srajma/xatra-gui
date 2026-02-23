#!/bin/bash
set -euo pipefail
trap 'kill 0' EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${XATRA_BACKEND_PORT:-8088}"
BACKEND_HOST="${XATRA_BACKEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${XATRA_FRONTEND_PREVIEW_PORT:-4173}"
FRONTEND_HOST="${XATRA_FRONTEND_HOST:-127.0.0.1}"
PYTHON_BIN="python3.12"

# Load .env if present.
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/.env"
    set +a
    BACKEND_PORT="${XATRA_BACKEND_PORT:-$BACKEND_PORT}"
    BACKEND_HOST="${XATRA_BACKEND_HOST:-$BACKEND_HOST}"
    FRONTEND_PORT="${XATRA_FRONTEND_PREVIEW_PORT:-$FRONTEND_PORT}"
    FRONTEND_HOST="${XATRA_FRONTEND_HOST:-$FRONTEND_HOST}"
fi

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
uv sync

if [ -f "../xatra.master/pyproject.toml" ]; then
    echo "Installing local xatra from ../xatra.master (editable)..."
    uv add --editable ../xatra.master
elif [ -f "../xatra/pyproject.toml" ]; then
    echo "Installing local xatra from ../xatra (editable)..."
    uv add --editable ../xatra
fi

free_port() {
    local port="$1"
    if command -v fuser >/dev/null 2>&1; then
        fuser -k "$port"/tcp 2>/dev/null || true
    fi
    if command -v lsof >/dev/null 2>&1; then
        for pid in $(lsof -ti:"$port" 2>/dev/null); do
            kill -9 "$pid" 2>/dev/null || true
        done
    fi
}

port_in_use() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti:"$port" >/dev/null 2>&1
    else
        fuser "$port"/tcp >/dev/null 2>&1
    fi
}

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    if port_in_use "$port"; then
        echo "Freeing port $port (killing existing process(es))..."
        free_port "$port"
        for i in 1 2 3 4 5; do
            sleep 1
            if ! port_in_use "$port"; then
                break
            fi
            if [ "$i" -eq 5 ]; then
                echo "ERROR: Port $port still in use. Try: kill -9 \$(lsof -ti:$port)"
                exit 1
            fi
            free_port "$port"
        done
    fi
done

echo "Starting Backend (${BACKEND_HOST}:$BACKEND_PORT)..."
python -m uvicorn main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &

echo "Building Frontend..."
cd "$SCRIPT_DIR/frontend"
if [ ! -d node_modules ]; then
    npm install
fi
npm run build

echo "Starting Frontend preview (${FRONTEND_HOST}:$FRONTEND_PORT)..."
npm run preview -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" &

wait
