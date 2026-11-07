"""FastAPI application entry point.

Dev:  uvicorn app.main:app --reload   (from backend/; the React app runs on Vite
      at :5173 and proxies /api here).
Prod: the same process ALSO serves the built React app (single service) — see
      the static mount at the bottom. Build the frontend first (npm run build),
      then everything is served from one origin, no CORS needed.
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import businesses, uploads


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the ML model off the request path at startup.

    The /ml endpoint imports shap + scikit-learn and builds a SHAP explainer the
    first time it's hit; doing it here means the first real request doesn't pay
    for it. Runs in a daemon thread so it never delays startup or readiness — the
    server starts listening (and /api/health responds) immediately, and the model
    finishes warming a beat later. Non-fatal: /ml keeps its existing lazy load.
    """
    # Surface our INFO logs (e.g. the ML warm-up confirmation) through uvicorn's
    # handler, so they appear alongside uvicorn's own startup output. We copy from
    # the "uvicorn" logger because "uvicorn.error" carries no handler of its own.
    app_logger = logging.getLogger("app")
    app_logger.handlers = logging.getLogger("uvicorn").handlers
    app_logger.setLevel(logging.INFO)

    from .ml import model as ml_model

    threading.Thread(target=ml_model.prewarm, name="ml-prewarm", daemon=True).start()
    yield


app = FastAPI(
    title="Undercurrent — Cash-Flow Underwriter",
    description="Explainable, alternative-data creditworthiness scoring for "
                "small businesses with seasonal or invoice-driven revenue.",
    version="1.0.0",
    lifespan=lifespan,
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
