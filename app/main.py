"""FastAPI server: exposes the chatbot API and serves the web frontend.

Run:
    uvicorn app.main:app --reload
"""
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config, rag

STATIC_DIR = config.BASE_DIR / "static"

app = FastAPI(title="Office Policy Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this if you host the frontend elsewhere
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


class Source(BaseModel):
    source: str
    page: int
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: list[Source]


@app.get("/api/health")
def health():
    return {"status": "ok", "indexed_chunks": rag.document_count()}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Plain `def` so FastAPI runs the blocking LLM call in a worker thread.
    if rag.document_count() == 0:
        raise HTTPException(
            status_code=503,
            detail="No documents indexed yet. Run `python -m app.ingest` first.",
        )
    session_id = req.session_id or str(uuid.uuid4())
    try:
        result = rag.ask(req.question.strip(), session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chatbot error: {exc}") from exc
    return ChatResponse(session_id=session_id, **result)


# Serve the frontend (index.html, style.css, app.js) at the site root.
# Mounted last so the /api routes above take priority.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
