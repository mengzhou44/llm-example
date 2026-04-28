from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from routers import analyze, chat, knowledge, mock_tickets  # noqa: E402 — must come after load_dotenv

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(mock_tickets.router)
