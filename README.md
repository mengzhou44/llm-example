# llm-example

A ChatGPT-style AI chat app with streaming responses, built with FastAPI and React.

![screenshot placeholder](https://placehold.co/800x450/212121/ececec?text=AI+Chat)

## Prerequisites

- Python 3.9+
- Node.js 18+
- An [Anthropic API key](https://console.anthropic.com/)

## Getting started

### 1. Clone the repo

```bash
git clone https://github.com/mengzhou44/llm-example.git
cd llm-example
```

### 2. Set up the ai-service

```bash
cd ai-service
cp .env.example .env          # then open .env and add your ANTHROPIC_API_KEY
pip3.11 install -r requirements.txt
```

### 3. Set up the frontend

```bash
cd frontend
npm install
```

### 4. Run

Open two terminals:

```bash
# Terminal 1 — ai-service (http://localhost:4000)
bash ai-service/start.sh

# Terminal 2 — frontend (http://localhost:3000)
cd frontend && npm run dev
```

Then open **http://localhost:3000** in your browser.

## Features

- **Streaming responses** — tokens appear in real time, just like ChatGPT
- **Conversation history** — context is maintained across messages within a session
- **Prompt templates** — switch between `helpful_assistant`, `code_reviewer`, and `teacher` from the sidebar
- **New chat** — start a fresh session at any time

## Adding a new template

Edit `ai-service/prompts.yaml` and add a new key:

```yaml
templates:
  helpful_assistant: "You are a helpful, friendly assistant..."
  my_template: "You are a ..."   # ← add here
```

Then add the key to the `TEMPLATES` array in `frontend/src/App.jsx`:

```js
const TEMPLATES = ["helpful_assistant", "code_reviewer", "teacher", "my_template"];
```

## API reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Single-turn chat, returns JSON |
| `/chat/stream` | POST | Multi-turn streaming chat (SSE) |

See [CLAUDE.md](./CLAUDE.md) for full API details.
