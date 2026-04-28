# llm-example

A ChatGPT-style AI chat app with RAG (knowledge base): Spring Boot gateway + FastAPI AI service with streaming SSE, React + Tailwind frontend.

## Architecture

```
React (port 3000)
    │  HTTP + SSE  (X-Auth-Token header)
    ▼
Spring Boot Gateway (port 4000)   ← auth stub, request validation, API management
    │  HTTP proxy
    ▼
FastAPI AI Service (port 5000)    ← Claude, RAG, tool use, session history
    │  httpx loopback
    ▼
/mock/tickets  (internal, same FastAPI process)
```

The Spring Boot gateway is the single entry point for the frontend. It validates the `X-Auth-Token` header on every request, then proxies AI endpoints (`/chat`, `/chat/stream`, `/knowledge/*`, `/analyze/*`) to the Python service. SSE streaming is proxied transparently at the byte level so the frontend receives the exact same wire format from FastAPI.

## GitHub operations
Always use the GitHub MCP server tools (e.g. mcp__github__create_pull_request, mcp__github__get_pull_request, etc.) for all GitHub interactions — pull requests, issues, branches, reviews, and file operations. Do NOT use the gh CLI for GitHub tasks.

## Stack

- **Gateway**: Java 21 + Spring Boot 3.2 + WebClient (spring-boot-starter-webflux)
- **AI service**: Python 3.11 + FastAPI + Anthropic SDK (Claude Haiku) + httpx + sentence-transformers + python-dotenv + PyYAML
- **Frontend**: React 18 + Vite + Tailwind CSS v3 + react-markdown + remark-gfm

## Setup

```bash
# AI service
cp ai-service/.env.example ai-service/.env   # add your ANTHROPIC_API_KEY
pip3.11 install -r ai-service/requirements.txt

# Gateway (requires Java 21 and Maven 3.x)
cd backend && mvn install -DskipTests

# Frontend
cd frontend && npm install
```

## Run

```bash
# AI service (port 5000)
bash ai-service/start.sh

# Gateway (port 4000)
bash backend/start.sh

# Frontend (port 3000)
cd frontend && npm run dev
```

## Authentication

All requests from the frontend must include the header `X-Auth-Token: dev-token-123`. The gateway returns `401` if the header is missing or incorrect. The token value is configured in `backend/src/main/resources/application.properties` (`auth.token`). This is a lightweight stub — replace with a real auth mechanism before production use.

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
Streaming SSE endpoint with multi-turn session history, prompt templates, intelligent RAG routing, and source transparency.
```json
// Request
{ "message": "Hello!", "session_id": "abc123", "template": "helpful_assistant" }
// SSE stream — first event carries routing decision, then token deltas
data: {"source": "both"}
data: {"delta": "Hello"}
data: [DONE]
```
`source` values: `"both"` (KB context injected + AI general knowledge), `"general_ai"` (no KB retrieval).

Available templates: `helpful_assistant`, `code_reviewer`, `teacher` — defined in `ai-service/prompts.yaml`. Add a new key there to create a new template; also add it to the `TEMPLATES` array in `frontend/src/App.jsx`.

**Session management**: conversation history is stored in memory keyed by `session_id`. The frontend generates a UUID on first load and persists it in `localStorage` so the session survives page reloads. Oldest messages are silently dropped when history exceeds the ~7168 token budget.

**Concurrency**: each session is protected by an `asyncio.Lock` to prevent concurrent requests from corrupting history order.

**RAG + intelligent routing**: before retrieval, a fast YES/NO classifier call (same Claude model, `max_tokens=5`) decides whether the query warrants a KB lookup. Personal/document-specific questions retrieve from the KB; general questions skip retrieval entirely. If KB is empty the classifier is never called. Falls back to using KB on classifier failure. The routing decision is returned as the first SSE event `{"source": "both"|"general_ai"}` and displayed as a pill badge in the UI.

**AI agent tool use**: Claude is given a set of tools on every `/chat/stream` call. If it decides to use a tool (`stop_reason == "tool_use"`), the AI service executes the tool, feeds the result back, and streams the final answer. A `{"tool_call": {"name": "...", "input": {...}}}` SSE event is emitted before each execution so the UI can show a progress indicator. Tool-use turns are stored in session history so follow-up questions have full context.

Available tools:
- `get_support_ticket` — fetch a single support ticket by ID
- `list_support_tickets` — list tickets, optionally filtered by status (`Open`, `In Progress`, `Resolved`)
- `update_ticket_status` — update ticket status (and optional resolution note); valid statuses: `Open`, `In Progress`, `Resolved`

Tool implementations live in `ai-service/tools/`. Adding a new tool requires: (1) a definition + implementation in `ai-service/tools/`, (2) registering it in `ai-service/tools/__init__.py`, (3) updating `formatToolCall` in `frontend/src/App.jsx` for the UI label.

### GET /mock/tickets
List all mock support tickets. Accepts optional `?status=Open|In Progress|Resolved` query param.

### GET /mock/tickets/{ticket_id}
Fetch a single mock support ticket by numeric ID (1001–1005).

### POST /mock/tickets/{ticket_id}/update
Update a mock ticket's status and optional resolution note.
```json
// Request
{ "status": "Resolved", "resolution": "Fixed in v2.4.0" }
// Response — full updated ticket object
```
Valid statuses: `Open`, `In Progress`, `Resolved`. Changes are in-memory only (reset on restart).

### POST /analyze/issue
Analyze a support ticket and return structured AI insights.
```json
// Request
{ "description": "Users report the login page fails to load on Safari 17+." }
// Also accepts a ticket ID reference: { "description": "analyze ticket 1001" }
// Response
{ "summary": "...", "root_cause": "...", "suggestion": "...", "ticket_id": "1001" }
```
`ticket_id` is present only when a mock ticket was resolved by ID; otherwise `null`. The endpoint auto-detects numeric IDs in the input (e.g. "analyze ticket 1001"), fetches the ticket from `/mock/tickets`, and sends the formatted content to Claude. The AI prompt lives in `prompts.yaml` under the `issue_analyzer` key.

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

All tunable values are in `ai-service/.env` (see `.env.example` for defaults):

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
- **Markdown rendering**: assistant responses are rendered via `react-markdown` + `remark-gfm` — supports code blocks, lists, bold/italic, tables, blockquotes. User messages remain plain text. Styles live in `.markdown-body` in `App.css`.
- Source badge under each assistant message: purple "Knowledge Base + AI" or gray "General AI"
- Tool call indicator (italic `↳ Fetching…` line) shown in assistant bubble when a tool is executing
- Sidebar: Chat/Analyzer mode toggle, template dropdown, Knowledge Base section (upload + document list), "New chat" button
- **Issue Analyzer mode**: paste raw ticket text or type a ticket ID (e.g. "analyze ticket 1001"); displays a structured result card with Summary, Root Cause, and Suggestion sections; shows a Ticket # header when an ID was resolved automatically
- Footer: "Easy Express Solutions Inc. © 2026"
- Enter to send, Shift+Enter for newline; blinking cursor while streaming
- Auto-resizing textarea: grows up to 192px as the user types, resets to one row on send

## MCP servers

Configured in `.mcp.json` (gitignored):
- **github** — `@modelcontextprotocol/server-github` via npx, uses `GITHUB_PERSONAL_ACCESS_TOKEN`
- **jira** — `mcp-atlassian` via uvx, connected to `mengzhou.atlassian.net`

Restart Claude Code after editing `.mcp.json` for changes to take effect.

## Project structure

```
ai-service/
  main.py              # FastAPI app setup, CORS, router registration
  routers/
    chat.py            # /chat, /chat/stream — session history, RAG injection, tool-use loop
    knowledge.py       # /knowledge/* — upload, list, delete, search
    mock_tickets.py    # /mock/tickets — mock external support ticket system
    analyze.py         # /analyze/issue — Issue Analyzer: ticket ID lookup + Claude structured output
  tools/
    __init__.py        # Tool registry (TOOLS list) + execute_tool dispatcher
    support_tickets.py # get_support_ticket and list_support_tickets definitions + httpx impl
  prompts.yaml         # System prompt templates
  requirements.txt     # Python dependencies
  start.sh             # Start the AI service (port 5000, python3.11)
  .env                 # API keys and config (gitignored)
  .env.example         # Template for .env
backend/
  pom.xml              # Maven build (Spring Boot 3.2, Java 21)
  start.sh             # Start the gateway (port 4000, mvn spring-boot:run)
  src/main/java/com/aiplatform/gateway/
    GatewayApplication.java          # Spring Boot entry point
    config/
      WebClientConfig.java           # WebClient bean → http://localhost:5000
      CorsConfig.java                # CORS filter (order 0, allows localhost:3000)
    filter/
      AuthenticationFilter.java      # X-Auth-Token header check (order 1)
    controller/
      ChatController.java            # /chat, /chat/stream (byte-level SSE proxy)
      KnowledgeController.java       # /knowledge/* proxy
      AnalyzeController.java         # /analyze/issue proxy
  src/main/resources/
    application.properties           # server.port=4000, ai.service.url, auth.token
frontend/
  src/
    App.jsx            # Chat UI + Issue Analyzer mode + Knowledge Base sidebar section
    App.css            # Tailwind directives + cursor-blink keyframe + .markdown-body prose styles
    main.jsx           # React entry point
  index.html
  package.json
  vite.config.js
  tailwind.config.js
  postcss.config.js
.mcp.json              # MCP server config (gitignored — contains secrets)
README.md              # Getting started guide
```
