# llm-example

A FastAPI service that exposes a `POST /chat` endpoint backed by Claude (Anthropic).

## Stack

- Python 3 + FastAPI
- Anthropic SDK (Claude Haiku)
- python-dotenv for config

## Setup

```bash
cp .env.example .env   # add your ANTHROPIC_API_KEY
pip3 install -r requirements.txt
```

## Run

```bash
bash scripts/start.sh
```

Server starts on `http://localhost:4000`.

## API

### POST /chat

Request:
```json
{ "message": "Hello!" }
```

Response:
```json
{ "response": "Hello! How can I help you today?" }
```

## Project structure

```
main.py            # FastAPI app and /chat endpoint
requirements.txt   # Python dependencies
scripts/start.sh   # Start the server
.env               # API keys (gitignored)
.env.example       # Template for .env
```
