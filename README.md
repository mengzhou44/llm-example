# AI Chat Platform

A production-style AI chat application with streaming responses, a retrieval-augmented knowledge base, AI agent tool use, and a structured issue analyzer — built across a three-tier architecture.

![Java](https://img.shields.io/badge/Java_21-Spring_Boot_3.2-ED8B00?logo=openjdk&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.11-FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React_18-Vite-61DAFB?logo=react&logoColor=black)
![Claude](https://img.shields.io/badge/Claude-Haiku-blueviolet)

<!-- Screenshot: main chat window with a streaming response and source badge visible -->
![Chat interface](docs/screenshot-chat.png)

---

## Architecture

```
React (port 3000)
    │  HTTP + SSE  (X-Auth-Token header)
    ▼
Spring Boot Gateway (port 4000)   ← auth, request validation, API management
    │  HTTP proxy
    ▼
FastAPI AI Service (port 5001)    ← Claude, RAG, tool use, session history
    │  httpx loopback
    ▼
/mock/tickets  (same FastAPI process)
```

The **Spring Boot gateway** is the single entry point for the frontend. It validates the `X-Auth-Token` header on every request and proxies all AI endpoints to the Python service. SSE streaming is proxied transparently at the byte level.

The **FastAPI AI service** runs Claude (Haiku), manages per-session conversation history, performs RAG retrieval, executes agent tools, and streams results back as Server-Sent Events.

---

## Features

| Feature | Description |
|---|---|
| **Streaming chat** | Tokens appear in real time via SSE, just like ChatGPT |
| **Session history** | Conversation context maintained per session with token-budget management |
| **Prompt templates** | Switch between `helpful_assistant`, `code_reviewer`, and `teacher` |
| **Intelligent RAG routing** | A fast YES/NO classifier decides whether to retrieve from the knowledge base before each response |
| **Knowledge base** | Upload `.txt`, `.md`, `.pdf`, or `.docx` files; chunked, embedded, and semantically searched |
| **AI agent tool use** | Claude calls backend APIs to fetch, list, and update support tickets |
| **Structured reasoning** | Multi-step pipeline: intent analysis → retrieval → response generation → validation → retry |
| **Issue Analyzer** | Paste a ticket description to receive structured summary, root cause, and suggestion |
| **Resilience** | Retry logic, circuit breaker, structured error responses, graceful shutdown |
| **Markdown rendering** | Assistant responses render as formatted markdown with code blocks, tables, and lists |

<!-- Screenshot: Issue Analyzer tab with a filled result card -->
![Issue Analyzer](docs/screenshot-analyzer.png)

---

## Prerequisites

| Dependency | Version | Notes |
|---|---|---|
| Java | 21 | Required by Spring Boot gateway |
| Maven | 3.x | `mvn -version` to verify |
| Python | **3.11 exactly** | Start scripts hard-pin `python3.11` |
| Node.js | 18+ | For the React frontend |
| Anthropic API key | — | [Get one here](https://console.anthropic.com/) |

---

## Quick start

### 1. Clone the repo

```bash
git clone https://github.com/mengzhou44/llm-example.git
cd llm-example
```

### 2. Configure the AI service

```bash
cp ai-service/.env.example ai-service/.env
# Open ai-service/.env and set ANTHROPIC_API_KEY=your_key_here
```

### 3. Install dependencies

```bash
# Python dependencies
pip3.11 install -r ai-service/requirements.txt

# Maven dependencies (downloads on first run, ~2 min)
cd backend && mvn -q dependency:resolve && cd ..

# Node dependencies
cd frontend && npm install && cd ..
```

### 4. Run — one command

```bash
bash start.sh
```

This starts all three services and prints their URLs. Open **http://localhost:3000** when the gateway is ready (~30 s on first compile).

**Or run each service manually in three terminals:**

```bash
# Terminal 1 — AI service (port 5001)
bash ai-service/start.sh

# Terminal 2 — Spring Boot gateway (port 4000)
bash backend/start.sh

# Terminal 3 — Frontend (port 3000)
cd frontend && npm run dev
```

> **First upload note:** the first document upload triggers a one-time download of the `all-MiniLM-L6-v2` embedding model (~80 MB). Subsequent uploads are instant.

---

## Authentication

All requests from the frontend include `X-Auth-Token: dev-token-123`. The gateway returns `401` if the header is missing or incorrect.

To use a custom token, set the `AUTH_TOKEN` environment variable before starting the gateway:

```bash
AUTH_TOKEN=my-secret bash backend/start.sh
```

Then set the matching value in `frontend/.env`:

```bash
cp frontend/.env.example frontend/.env
# Set VITE_AUTH_TOKEN=my-secret
```

---

## Configuration

All tunable values live in `ai-service/.env` (copy from `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required** |
| `MODEL` | `claude-haiku-4-5-20251001` | Claude model |
| `MAX_TOKENS` | `1024` | Max response tokens |
| `CONTEXT_TOKEN_BUDGET` | `7168` | Session history token limit |
| `CHUNK_SIZE` | `500` | KB chunk size in characters |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `KB_TOP_K` | `3` | Number of KB chunks retrieved per query |
| `KB_MIN_SCORE` | `0.35` | Minimum similarity score for retrieval |
| `MAX_UPLOAD_BYTES` | `10485760` | Upload size limit (10 MB) |
| `ENABLE_VALIDATION` | `true` | Enable response validation + retry |
| `THINKING_BUDGET_TOKENS` | `2000` | Token budget for reasoning steps |

---

## API reference

All endpoints are accessed through the gateway at `http://localhost:4000`. Every request requires the `X-Auth-Token` header.

### Chat

| Endpoint | Method | Description |
|---|---|---|
| `/chat` | POST | Single-turn chat, returns JSON `{ "response": "..." }` |
| `/chat/stream` | POST | Multi-turn streaming chat (SSE). Body: `{ "message", "session_id", "template" }` |

The streaming endpoint emits a sequence of SSE events:
```
data: {"step": "analyzing"}
data: {"source": "both"}          ← routing decision ("both" or "general_ai")
data: {"tool_call": {"name": "get_support_ticket", "input": {...}}}
data: {"delta": "Hello"}          ← token-by-token response
data: [DONE]
```

### Knowledge Base

| Endpoint | Method | Description |
|---|---|---|
| `/knowledge/upload` | POST | Upload a document (multipart/form-data, field `file`) |
| `/knowledge/documents` | GET | List all uploaded documents |
| `/knowledge/documents/{id}` | DELETE | Remove a document and its chunks |
| `/knowledge/search` | POST | Semantic search. Body: `{ "query", "top_k" }` |

### Issue Analyzer

| Endpoint | Method | Description |
|---|---|---|
| `/analyze/issue` | POST | Analyze a ticket. Body: `{ "description" }`. Auto-resolves ticket IDs (e.g. "analyze ticket 1001"). Returns `{ "summary", "root_cause", "suggestion", "ticket_id" }` |

### Mock Ticket System

| Endpoint | Method | Description |
|---|---|---|
| `/mock/tickets` | GET | List tickets. Optional `?status=Open\|In Progress\|Resolved` |
| `/mock/tickets/{id}` | GET | Fetch ticket by ID (1001–1005) |
| `/mock/tickets/{id}/update` | POST | Update status. Body: `{ "status", "resolution" }` |

### Health

| Endpoint | Method | Description |
|---|---|---|
| `/actuator/health` | GET | Spring Boot gateway health |
| `/health` | GET | FastAPI AI service health (direct, port 5001) |

---

## Adding a prompt template

Edit `ai-service/prompts.yaml`:

```yaml
templates:
  helpful_assistant: "You are a helpful, friendly assistant…"
  my_template: "You are a …"   # ← add here
```

Then add the key to `frontend/src/components/Sidebar.jsx`:

```js
const TEMPLATES = ["helpful_assistant", "code_reviewer", "teacher", "my_template"];
```

---

## Project structure

```
ai-service/
  main.py              # FastAPI app, CORS, graceful shutdown
  routers/
    chat.py            # /chat, /chat/stream — session history, RAG, tool-use loop
    knowledge.py       # /knowledge/* — upload, list, delete, search
    mock_tickets.py    # /mock/tickets — mock support ticket system
    analyze.py         # /analyze/issue — Issue Analyzer
  tools/
    __init__.py        # Tool registry + dispatcher
    support_tickets.py # Ticket tool definitions and httpx implementations
  prompts.yaml         # System prompt templates
  requirements.txt
  start.sh             # Start AI service (port 5001)
  .env.example
backend/
  pom.xml
  start.sh             # Start gateway (port 4000)
  src/main/java/com/aiplatform/gateway/
    config/            # WebClient, CORS
    filter/            # Auth token check
    controller/        # /chat, /knowledge/*, /analyze/* proxy controllers
  src/main/resources/
    application.properties
frontend/
  src/
    App.jsx            # State, event handlers, top-level layout
    App.css            # Tailwind directives, markdown prose styles
    components/
      Sidebar.jsx      # Mode toggle, template selector, new chat
      KnowledgeBase.jsx # Upload + document list with delete confirmation
      MessageList.jsx  # Scrollable chat area with welcome screen
      MessageBubble.jsx # Single message — user/assistant, tool calls, source badge
      ChatInput.jsx    # Auto-resize textarea + send button
      WelcomeScreen.jsx # Empty state with suggested prompt chips
      IssueAnalyzer.jsx # Issue Analyzer mode with skeleton loading
  index.html
  .env.example
start.sh               # One-command start for all three services
```

<!-- Screenshot: tool-use indicator in a chat message showing "✓ Fetched support ticket #1001" -->
![Tool use](docs/screenshot-tool-use.png)

---

## Tech stack

- **Gateway**: Java 21 · Spring Boot 3.2 · WebFlux WebClient · Actuator
- **AI service**: Python 3.11 · FastAPI · Anthropic SDK · sentence-transformers · httpx
- **Frontend**: React 18 · Vite · Tailwind CSS v3 · react-markdown
- **AI model**: Claude Haiku (claude-haiku-4-5-20251001)
