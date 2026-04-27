# llm-example

A ChatGPT-style AI chat app: FastAPI backend with streaming SSE, React frontend.


## GitHub operations
Always use the GitHub MCP server tools (e.g. mcp__github__create_pull_request, mcp__github__get_pull_request, etc.) for all GitHub interactions — pull requests, issues, branches, reviews, and file operations. Do NOT use the gh CLI for GitHub tasks.

## Stack

- **Backend**: Python 3 + FastAPI + Anthropic SDK (Claude Haiku) + python-dotenv + PyYAML
- **Frontend**: React 18 + Vite

## Setup

```bash
# Backend
cp backend/.env.example backend/.env   # add your ANTHROPIC_API_KEY
pip3 install -r backend/requirements.txt

# Frontend
cd frontend && npm install
```

## Run

```bash
# Backend (port 4000)
bash backend/scripts/start.sh

# Frontend (port 5173)
cd frontend && npm run dev
```

## API

### POST /chat
Simple single-turn chat (no history).
```json
// Request
{ "message": "Hello!" }
// Response
{ "response": "Hello! How can I help you today?" }
```

### POST /chat/stream
Streaming SSE endpoint with multi-turn session history and prompt templates.
```json
// Request
{ "message": "Hello!", "session_id": "abc123", "template": "helpful_assistant" }
// SSE stream
data: {"delta": "Hello"}
data: [DONE]
```

Available templates: `helpful_assistant`, `code_reviewer`, `teacher` — defined in `backend/prompts.yaml`.

**Session management**: conversation history is stored in memory keyed by `session_id`. The frontend generates a UUID and persists it in `localStorage` so the session survives page reloads. Oldest messages are dropped when the history exceeds the token budget (~7168 tokens).

**Concurrency**: each session is protected by an `asyncio.Lock` to prevent concurrent requests from corrupting history order.

## Frontend (PL-12)

React 18 + Vite single-page app at `http://localhost:5173`.

- Streams token-by-token using `fetch` + `ReadableStream` (SSE over POST)
- Template selector in sidebar (maps to `backend/prompts.yaml` keys)
- "New chat" button resets the session and clears history
- Auto-scrolls to latest message; blinking cursor while streaming
- Enter to send, Shift+Enter for newline

## Project structure

```
backend/
  main.py            # FastAPI app: /chat and /chat/stream endpoints
  prompts.yaml       # System prompt templates (add new keys here to extend)
  requirements.txt   # Python dependencies
  scripts/start.sh   # Start the backend server
  .env               # API keys (gitignored)
  .env.example       # Template for .env
frontend/
  src/
    App.jsx          # Chat UI: messages, template selector, streaming, session
    App.css          # Dark ChatGPT-style theme
    main.jsx         # React entry point
  index.html
  package.json
  vite.config.js
```
