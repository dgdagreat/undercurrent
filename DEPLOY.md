# Deploying Undercurrent to Google Cloud Run

Undercurrent is a single, stateless Docker container (React built and served by
the FastAPI process; the SQLite DB and the ML model are baked into the image at
build time). That makes [Cloud Run](https://cloud.google.com/run) an ideal host:
it builds straight from the `Dockerfile`, scales on demand, and — with one flag —
keeps an instance warm so a resume/portfolio link never greets a visitor with a
cold-start spinner.

Nothing in the app needs changing first:

- The frontend calls the API with **relative** `/api/...` paths, so single-origin
  serving on Cloud Run works out of the box (no CORS, no API base URL to set).
- The container listens on **`$PORT`** (`uvicorn ... --port ${PORT:-8000}`), which
  Cloud Run injects automatically — no `--port` flag needed.

---

## One-time setup

You need the [gcloud CLI](https://cloud.google.com/sdk/docs/install), a GCP
project with billing enabled, and the Cloud Run + Cloud Build APIs turned on.

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

---

## Deploy (always-warm — recommended for a demo link)

`--source .` hands the repo to Cloud Build, which uses this project's
`Dockerfile`. `--min-instances 1` keeps one instance alive so there is **no
cold start** for visitors.

```bash
gcloud run deploy undercurrent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 1 \
  --memory 1Gi \
  --cpu 1
```

When it finishes, gcloud prints a public `https://undercurrent-....run.app` URL.
That's your live demo.

- Pick the `--region` nearest your audience (e.g. `us-east1`, `europe-west1`).
- `--memory 1Gi` gives shap/scikit-learn/pandas headroom. The app warms the ML
  model at startup (a daemon-thread hook in `main.py`), so that memory is held
  for the instance's life rather than on the first `/ml` call — 512Mi can be
  tight. Drop to `--memory 512Mi` to economize if you don't hit OOMs.
- CPU is allocated only during requests by default, so the warm idle instance
  stays cheap (see cost note below).

## Deploy (scale-to-zero — cheapest, but first visitor waits)

Omit `--min-instances` and the service scales to zero when idle. You pay almost
nothing, but the first request after idle waits for the container to spin up (a
few seconds) plus the first ML call's library load.

```bash
gcloud run deploy undercurrent --source . --region us-central1 --allow-unauthenticated --memory 1Gi
```

---

## Keeping it warm without `--min-instances` (free-tier trick)

If you'd rather run scale-to-zero (or host on a free tier elsewhere) but still
avoid cold starts, point a free uptime pinger (UptimeRobot, cron-job.org) at the
health endpoint every ~10 minutes so the instance never idles out:

```
https://undercurrent-xxxx.run.app/api/health
```

---

## Redeploy and teardown

Redeploy after changes — same command:

```bash
gcloud run deploy undercurrent --source . --region us-central1 --allow-unauthenticated --min-instances 1 --memory 1Gi --cpu 1
```

Tear it down completely:

```bash
gcloud run services delete undercurrent --region us-central1
```

---

## Cost, roughly

Cloud Run bills per request and per resource-second, with a monthly free tier
(2M requests, 360K GiB-seconds of memory, 180K vCPU-seconds). A scale-to-zero
demo typically costs **$0**. With `--min-instances 1`, one 1-GiB instance is
*allocated* 24/7 but — because CPU is throttled to zero between requests by
default — the ongoing charge is small (roughly a few dollars a month for the
reserved memory; check current pricing for your region). For a resume link, the
always-warm option is usually worth it.

> This is a portfolio demo. Any re-scores or uploads write to the in-image
> SQLite and reset when the container restarts — expected behavior here. A real
> deployment would move state to managed Postgres (Cloud SQL).
