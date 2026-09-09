# Single-service image: builds the React app, then serves it + the API from one
# FastAPI/uvicorn process. Deploys as-is on Render, Railway, Fly, or any Docker
# host. The DB (and its cached scores) is seeded at build time; the ML model
# artifact is committed, so /ml works out of the box.

# --- Stage 1: build the frontend ---------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend + serve ------------------------------------------------
FROM python:3.11-slim
WORKDIR /app

# System deps for numpy/scipy/llvmlite wheels are already prebuilt; keep it lean.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY --from=frontend /app/frontend/dist frontend/dist

# Seed the SQLite DB (30 businesses + cached scores) into the image so the app
# is ready the instant the container boots — no cold-start seeding.
RUN cd backend && python -m app.seed

ENV PORT=8000
EXPOSE 8000
# Hosts inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "cd backend && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
