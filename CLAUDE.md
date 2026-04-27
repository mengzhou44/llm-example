# llm-example

A ChatGPT-style AI chat app: FastAPI backend with streaming SSE, React frontend.

## Stack

- **Backend**: Python 3 + FastAPI + Anthropic SDK (Claude Haiku) + python-dotenv
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
Streaming SSE chat with session history and prompt templates.
```json
// Request
{ "message": "Hello!", "session_id": "abc123", "template": "helpful_assistant" }
// SSE stream
data: {"delta": "Hello"}
data: [DONE]
```

Available templates: `helpful_assistant`, `code_reviewer`, `teacher` — defined in `backend/prompts.yaml`.

## Project structure

```
backend/
  main.py            # FastAPI app: /chat and /chat/stream endpoints
  prompts.yaml       # System prompt templates
  requirements.txt   # Python dependencies
  scripts/start.sh   # Start the backend server
  .env               # API keys (gitignored)
  .env.example       # Template for .env
frontend/
  src/
    App.jsx          # Chat UI (messages, template selector, streaming)
    App.css          # Styles
    main.jsx         # React entry point
  index.html
  package.json
  vite.config.js
```
