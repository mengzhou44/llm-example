# llm-example

A ChatGPT-style AI chat app with RAG (knowledge base): FastAPI backend with streaming SSE, React + Tailwind frontend.


## GitHub operations
Always use the GitHub MCP server tools (e.g. mcp__github__create_pull_request, mcp__github__get_pull_request, etc.) for all GitHub interactions — pull requests, issues, branches, reviews, and file operations. Do NOT use the gh CLI for GitHub tasks.

## Stack

- **Backend**: Python 3.11 + FastAPI + Anthropic SDK (Claude Haiku) + sentence-transformers + python-dotenv + PyYAML
- **Frontend**: React 18 + Vite + Tailwind CSS v3

## Setup

```bash
# Backend
cp backend/.env.example backend/.env   # add your ANTHROPIC_API_KEY
pip3.11 install -r backend/requirements.txt

# Frontend
cd frontend && npm install
```

## Run

```bash
# Backend (port 4000)
bash backend/start.sh

# Frontend (port 3000)
cd frontend && npm run dev
```

## API

### POST /chat
Simple single-turn chat, no history.
```json
// Request
{ "message": "Hello!" }
// Response
{ "response": "Hello! How can I help you today?" }
```

### POST /chat/stream
Streaming SSE endpoint with multi-turn session history, prompt templates, and automatic RAG context injection.
```json
// Request
{ "message": "Hello!", "session_id": "abc123", "template": "helpful_assistant" }
// SSE stream
data: {"delta": "Hello"}
data: [DONE]
```

Available templates: `helpful_assistant`, `code_reviewer`, `teacher` — defined in `backend/prompts.yaml`. Add a new key there to create a new template; also add it to the `TEMPLATES` array in `frontend/src/App.jsx`.

**Session management**: conversation history is stored in memory keyed by `session_id`. The frontend generates a UUID on first load and persists it in `localStorage` so the session survives page reloads. Oldest messages are silently dropped when history exceeds the ~7168 token budget.

**Concurrency**: each session is protected by an `asyncio.Lock` to prevent concurrent requests from corrupting history order.

**RAG**: on each chat message, the top-3 most relevant knowledge base chunks (cosine similarity ≥ 0.2) are injected into the system prompt automatically. If the KB is empty, chat works as normal.

### POST /knowledge/upload
Upload a document (.txt, .md, .pdf, .docx — max 10 MB). Text is extracted, split into 500-char chunks with 50-char overlap, and embedded via `sentence-transformers` (`all-MiniLM-L6-v2`). Returns document metadata.

### GET /knowledge/documents
List all uploaded documents (id, name, uploaded_at, chunk_count).

### DELETE /knowledge/documents/{doc_id}
Remove a document and all its chunks from the knowledge base.

### POST /knowledge/search
Semantic search over the knowledge base.
```json
// Request
{ "query": "Python experience", "top_k": 5 }
// Response
[{ "doc_id": "...", "doc_name": "resume.pdf", "text": "...", "score": 0.87 }]
```

**Knowledge base**: all documents and embeddings are stored in memory — wiped on server restart. The embedding model (~80 MB) is downloaded on first upload.

## Configuration

All tunable values are in `backend/.env` (see `.env.example` for defaults):

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required |
| `MODEL` | `claude-haiku-4-5-20251001` | Claude model |
| `MAX_TOKENS` | `1024` | Max response tokens |
| `CONTEXT_TOKEN_BUDGET` | `7168` | Session history token limit |
| `CHUNK_SIZE` | `500` | KB chunk size in characters |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `MAX_UPLOAD_BYTES` | `10485760` | Upload size limit (10 MB) |

## Frontend

React 18 + Vite + Tailwind CSS v3 SPA at `http://localhost:3000`.

- Light mode theme (white/gray-50 background, blue user bubbles)
- Streams token-by-token via `fetch` + `ReadableStream` (SSE over POST)
- Sidebar: template dropdown, Knowledge Base section (upload + document list), "New chat" button
- Footer: "Easy Express Solutions Inc. © 2026"
- Enter to send, Shift+Enter for newline; blinking cursor while streaming

## MCP servers

Configured in `.mcp.json` (gitignored):
- **github** — `@modelcontextprotocol/server-github` via npx, uses `GITHUB_PERSONAL_ACCESS_TOKEN`
- **jira** — `mcp-atlassian` via uvx, connected to `mengzhou.atlassian.net`

Restart Claude Code after editing `.mcp.json` for changes to take effect.

## Project structure

```
backend/
  main.py              # FastAPI app setup, CORS, router registration
  routers/
    chat.py            # /chat, /chat/stream — session history + RAG injection
    knowledge.py       # /knowledge/* — upload, list, delete, search
  prompts.yaml         # System prompt templates
  requirements.txt     # Python dependencies
  start.sh             # Start the backend server (port 4000, python3.11)
  .env                 # API keys and config (gitignored)
  .env.example         # Template for .env
frontend/
  src/
    App.jsx            # Chat UI + Knowledge Base sidebar section
    App.css            # Tailwind directives + cursor-blink keyframe
    main.jsx           # React entry point
  index.html
  package.json
  vite.config.js
  tailwind.config.js
  postcss.config.js
.mcp.json              # MCP server config (gitignored — contains secrets)
README.md              # Getting started guide
```
