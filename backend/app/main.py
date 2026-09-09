"""FastAPI application entry point.

Dev:  uvicorn app.main:app --reload   (from backend/; the React app runs on Vite
      at :5173 and proxies /api here).
Prod: the same process ALSO serves the built React app (single service) — see
      the static mount at the bottom. Build the frontend first (npm run build),
      then everything is served from one origin, no CORS needed.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import businesses, uploads

app = FastAPI(
    title="Undercurrent — Cash-Flow Underwriter",
    description="Explainable, alternative-data creditworthiness scoring for "
                "small businesses with seasonal or invoice-driven revenue.",
    version="1.0.0",
)

# The Vite dev server runs on a different port, so allow it during development.
# In production the frontend is served from this same origin, so CORS is moot.
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


# Serve the built React app (single-service deploy). Registered LAST so it never
# shadows the /api routes or the auto docs. Only mounts if a build exists, so it
# stays out of the way in dev (where Vite serves the frontend). The app uses
# hash routing (#/…), so StaticFiles(html=True) at "/" is enough — every URL
# path is "/" and the fragment is client-side.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
