"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload   (from the backend/ directory)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import businesses, uploads

app = FastAPI(
    title="Pulse — Cash-Flow Underwriter",
    description="Explainable, alternative-data creditworthiness scoring for "
                "small businesses with seasonal or invoice-driven revenue.",
    version="1.0.0",
)

# The Vite dev server runs on a different port, so allow it during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(businesses.router)
app.include_router(uploads.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
