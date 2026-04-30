#!/bin/bash
# Starts all three services: AI service (5001), gateway (4000), frontend (3000).
# Prerequisites: Python 3.11, Java 21, Maven 3.x, Node.js 18+
# Press Ctrl+C to stop everything.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  echo ""
  echo "Stopping all services…"
  kill 0
}
trap cleanup INT TERM

echo "▶ Starting AI service on http://localhost:5001"
bash "$ROOT/ai-service/start.sh" &

echo "▶ Starting Spring Boot gateway on http://localhost:4000"
bash "$ROOT/backend/start.sh" &

echo "▶ Starting frontend on http://localhost:3000"
cd "$ROOT/frontend" && npm run dev &

echo ""
echo "All services starting. Open http://localhost:3000 when ready."
echo "Note: the gateway takes ~30 s on first start while Maven compiles."
echo ""
wait
