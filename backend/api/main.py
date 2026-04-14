"""
FastAPI backend for the CEAT 2W Tyre Recommender web app.
Provides a streaming SSE endpoint and a standard JSON endpoint.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rag_engine import TyreRAG

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="CEAT Tyre Recommender API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Vercel domain in production
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Single shared RAG instance (loaded at startup)
_rag: TyreRAG | None = None


@app.on_event("startup")
def startup():
    global _rag
    _rag = TyreRAG()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class HistoryMessage(BaseModel):
    role: str    # "user" | "assistant"
    content: str


class RecommendRequest(BaseModel):
    query: str
    history: Optional[List[HistoryMessage]] = []


class RecommendResponse(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "records": _rag._collection.count() if _rag else 0}


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    """Non-streaming endpoint — returns the full answer as JSON."""
    if not _rag:
        raise HTTPException(503, "Service initialising, please retry.")
    try:
        history = [m.model_dump() for m in req.history] if req.history else []
        answer = _rag.recommend(req.query, history=history)
        return RecommendResponse(answer=answer)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/recommend/stream")
async def recommend_stream(req: RecommendRequest):
    """
    Streaming SSE endpoint.
    Each event: data: {"token": "..."}
    Final event: data: {"done": true}
    """
    if not _rag:
        raise HTTPException(503, "Service initialising, please retry.")

    history = [m.model_dump() for m in req.history] if req.history else []

    def event_generator():
        try:
            for token in _rag.recommend_stream(req.query, history=history):
                payload = json.dumps({"token": token})
                yield f"data: {payload}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Entry point (for local dev)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
