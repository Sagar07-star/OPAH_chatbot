#!/usr/bin/env bash
# CREATEchat one-command launcher (Linux / macOS).
# Backend: http://127.0.0.1:8000   Frontend: http://localhost:5173
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Shutting down CREATEchat…"
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  echo "Stopped."
}
trap cleanup EXIT INT TERM

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "✗ $1 is required but not installed. $2"
    exit 1
  fi
}

echo "CREATEchat · OPAH prototype"
echo "----------------------------------------"
need python3 "Install Python 3.10+ (https://www.python.org/downloads/)."
need node "Install Node.js 18+ (https://nodejs.org)."
need npm "npm ships with Node.js."

PY_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "· Python $PY_VERSION, Node $(node -v), npm $(npm -v)"

if [[ ! -d backend/.venv ]]; then
  echo "· Creating the Python virtual environment"
  python3 -m venv backend/.venv
fi
PY="$ROOT/backend/.venv/bin/python"

if ! "$PY" -c "import fastapi, uvicorn, openai, pypdf, multipart, dotenv" >/dev/null 2>&1; then
  echo "· Installing backend dependencies"
  "$PY" -m pip install --upgrade pip >/dev/null
  "$PY" -m pip install -r backend/requirements.txt
else
  echo "· Backend dependencies already installed"
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "· Installing frontend dependencies"
  (cd frontend && npm install --no-audit --no-fund)
else
  echo "· Frontend dependencies already installed"
fi

if [[ ! -f .env ]]; then
  echo "· Creating .env from .env.example (add OPENAI_API_KEY for live replies)"
  cp .env.example .env
fi

if grep -qE '^OPENAI_API_KEY=.+' .env 2>/dev/null || grep -qE '^OPENAI_API_KEY=.+' backend/.env 2>/dev/null || [[ -n "${OPENAI_API_KEY:-}" ]]; then
  echo "· Model key found"
else
  echo "· No OPENAI_API_KEY yet — the app runs, chat replies stay disabled until you add one"
fi

if (exec 3<>/dev/tcp/127.0.0.1/8000) 2>/dev/null; then
  echo "✗ Port 8000 is already in use. Stop the other process and run this again."
  exit 1
fi
if (exec 3<>/dev/tcp/127.0.0.1/5173) 2>/dev/null; then
  echo "✗ Port 5173 is already in use. Stop the other process and run this again."
  exit 1
fi

echo "· Starting the FastAPI backend"
"$PY" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "✗ The backend exited during startup. Check the log above."
    exit 1
  fi
  sleep 0.5
done

echo "· Starting the React frontend"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

for _ in $(seq 1 60); do
  if curl -sf http://localhost:5173 >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

cat <<BANNER

----------------------------------------
  CREATEchat is running

  Frontend  http://localhost:5173
  Backend   http://127.0.0.1:8000
  API docs  http://127.0.0.1:8000/docs

  Demo accounts: clt_001 (Maya), clt_002 (Jordan), clt_003 (Sam)
  Add OPENAI_API_KEY to .env for live assistant replies.
  Press Ctrl+C to stop both servers.
----------------------------------------

BANNER

wait
