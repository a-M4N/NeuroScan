# NeuroScan Docker Setup & Deployment Guide

This guide describes how to spin up the entire NeuroScan infrastructure (FastAPI Backend + PostgreSQL + WeasyPrint PDF compiler + Grad-CAM inference engine) on a fresh system using Docker.

---------------------------------------

## 1. Prerequisites

1. **Docker Desktop** (version 24.0+ with Docker Compose v2) installed and running.
   - On Windows: Ensure WSL 2 backend is enabled in Docker Desktop settings.
   - On Linux: Ensure `docker` and `docker compose` plugins are installed.
2. **Node.js & pnpm** (v18+ / v20+ with pnpm v9+) for running the frontend developer server on the host.
3. **Google Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/)) for automated clinical narrative report generation.

---

## 2. Model Checkpoints

NeuroScan utilizes deep learning weights for disease classification:
- `models/checkpoints/tumor_classifier_brisc2025.pth` (~15.6 MB)
- `models/checkpoints/alzheimers_effnet_b0.pth` (~15.6 MB)

> [!NOTE]
> **Zero Manual Setup**: Because these checkpoints total only ~31.2 MB, they are baked directly into the Docker image via `COPY models/checkpoints/ ./models/checkpoints/` during `docker compose build`. On a fresh machine, cloning the repository and running `docker compose up --build` works immediately without requiring separate manual model downloads.
>
> The `./models/checkpoints` directory is also mounted as a volume in `docker-compose.yml`, so any updated weights placed on the host immediately take effect inside the container without rebuilding.

---

## 3. Quick Start (Fresh Machine)

### Step 1: Clone the Repository & Configure Environment
```bash
git clone <repository_url>
cd NeuroScan

# Create environment file from template
cp .env.example .env
```

Open `.env` and configure your credentials:
```env
POSTGRES_USER=neuroscan_admin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=neuroscan_db
POSTGRES_HOST=db
POSTGRES_PORT=5432
DATABASE_URL=postgresql://neuroscan_admin:your_secure_password@db:5432/neuroscan_db
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### Step 2: Build & Start Backend and Database
```bash
docker compose up --build -d
```

What this does automatically:
1. Builds the `api` image with Python 3.13-slim and installs Linux system libraries for WeasyPrint (`libpango`, `libcairo`, `libgdk-pixbuf`, `libffi8`, `fonts-liberation`) and OpenCV.
2. Pulls and starts PostgreSQL 16 on internal port 5432 (mapped to host port 5433 for external inspection).
3. Waits for the database healthcheck (`pg_isready`) before launching the API.
4. Automatically runs database schema migrations (`alembic upgrade head`) on startup.
5. Loads EfficientNet classification models into CPU memory and binds Uvicorn to `http://0.0.0.0:8000`.

### Step 3: Verify Backend Health
From the host machine, verify:
```bash
curl http://localhost:8000/health
```
Expected response:
```json
{"status":"ok","model_loaded":true}
```

---

## 4. Running the Frontend

The frontend runs directly on the host using Vite for instant HMR (Hot Module Replacement) and fast development iteration.

```bash
cd frontend
pnpm install
pnpm dev
```

Open your browser at `http://localhost:5173`. The frontend automatically proxies API calls to `http://localhost:8000`.

---

## 5. Persistence & Data Storage

All patient uploads, generated Grad-CAM heatmaps, and compiled clinical PDF reports persist on the host filesystem and within the Docker volume:
- **Database records**: Stored in Docker named volume `pgdata` (`/var/lib/postgresql/data`).
- **Scans & Images**: Stored in `./data/scans/` on the host.
- **Grad-CAM Saliency Maps**: Stored in `./data/heatmaps/` on the host.
- **Compiled PDF Reports**: Stored in `./data/reports/` on the host.

To restart containers without losing any data:
```bash
docker compose down
docker compose up -d
```

To perform a complete clean reset (wiping all database tables and volumes):
```bash
docker compose down -v
```

---

## 6. Discovered Gotchas & Workarounds

1. **WeasyPrint Native Libraries on Linux**:
   WeasyPrint requires Cairo, Pango, and GDK-PixBuf at the OS level. In `api/Dockerfile`, the runtime container installs `libpango-1.0-0`, `libpangoft2-1.0-0`, `libpangocairo-1.0-0`, `libcairo2`, `libgdk-pixbuf-2.0-0`, `libffi8`, `shared-mime-info`, and `fonts-liberation`.
2. **Missing `markdown` in `pyproject.toml`**:
   `api/core/pdf_export.py` converts Gemini's narrative markdown to HTML using the Python `markdown` package. `markdown>=3.6` has been pinned and locked in `uv.lock`.
3. **Protobuf Compatibility with TensorBoard & Google Generative AI**:
   `google-generativeai` requires `protobuf<6.0.0`, while recent `tensorboard` releases default to `protobuf>=6`. Tensorboard is pinned to `tensorboard>=2.18.0,<2.22.0` in `pyproject.toml` so `uv lock` resolves `protobuf==5.29.6` cleanly.
4. **Automatic Migration Execution**:
   To avoid requiring manual `alembic upgrade head` commands on a fresh machine, the Dockerfile executes migrations as part of the container entrypoint (`sh -c "alembic upgrade head && exec uvicorn api.main:app --host 0.0.0.0 --port 8000"`).
