#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --port 8000) &
(cd frontend && bun run dev --port 5174 --strictPort) &
wait
