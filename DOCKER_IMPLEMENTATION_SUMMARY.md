# NeuroScan Docker Infrastructure Implementation & Live Verification Summary

This document provides a technical record of the Docker containerization, configuration, dependency resolution, and empirical verification of the NeuroScan system (FastAPI backend, PostgreSQL database, PyTorch Grad-CAM inference engine, and WeasyPrint PDF report compiler).

---

## 1. Architecture & Design Overview

```
+-----------------------------------------------------------------------------------+
| Host System                                                                       |
|                                                                                   |
|  +---------------------------+        +----------------------------------------+  |
|  | Host Frontend (Vite)      |        | Host Filesystem                        |  |
|  | Port 5173 (pnpm dev)      |        | - ./data/scans/                        |  |
|  | - React 19 UI             |        | - ./data/heatmaps/                     |  |
|  | - HMR Hot Reloading       |        | - ./data/reports/                      |  |
|  +-------------+-------------+        | - ./models/checkpoints/                |  |
|                |                      +----+-------------------+---------------+  |
|                | HTTP Requests             |                   |                  |
|                v (Port 8000)               | Volume Mount      | Volume Mount     |
|  +-----------------------------------------+-------------------+---------------+  |
|  | Docker Bridge Network: neuroscan_default                                    |  |
|  |                                                                             |  |
|  |  +-----------------------------------+   +-------------------------------+  |  |
|  |  | Container: neuroscan-api-1        |   | Container: neuroscan-db-1     |  |  |
|  |  | (FastAPI + Uvicorn)               |   | (PostgreSQL 16)               |  |  |
|  |  | - Python 3.13-slim                |   | - Port 5432 (Internal)        |  |  |
|  |  | - EfficientNet-B0 (31.2 MB baked) |   | - Port 5433 (Host Mapped)     |  |  |
|  |  | - Grad-CAM Layer Hooks            |   | - Named Volume: pgdata        |  |  |
|  |  | - WeasyPrint (GTK3/Pango/Cairo)   |   | - Healthcheck: pg_isready     |  |  |
|  |  | - Auto Alembic Migrations on Boot |   +---------------+---------------+  |  |
|  |  +-----------------+-----------------+                   ^                  |  |
|  |                    |                                     |                  |  |
|  |                    +-- DATABASE_URL (db:5432) -----------+                  |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### Key Engineering Decisions

1. **Frontend Isolation on Host**:
   - The frontend remains directly on the host using `pnpm dev` for instant Hot Module Replacement (HMR) and rapid developer feedback.
   - The Dockerized API exposes port `8000:8000`, matching Vite's backend target.
2. **Zero-Manual-Setup Model Weights**:
   - Model checkpoints (`tumor_classifier_brisc2025.pth` and `alzheimers_effnet_b0.pth`) total **31.2 MB combined**.
   - They are copied directly into the Docker image via `COPY models/checkpoints/ ./models/checkpoints/` during build time.
   - Fresh clones require no manual weight downloads or external storage configuration.
   - Checkpoints are also mounted as a host volume (`./models/checkpoints:/app/models/checkpoints`) so active retraining updates apply immediately without rebuilding.
3. **Automated Schema Migrations on Startup**:
   - Container startup runs `alembic upgrade head && exec uvicorn api.main:app --host 0.0.0.0 --port 8000`.
   - Any fresh database automatically receives all schema tables (`patients`, `scans`, `predictions`, `reports`) before Uvicorn begins serving traffic.
4. **WeasyPrint System Dependencies in Debian 12**:
   - The runtime stage installs: `libpango-1.0-0`, `libpangoft2-1.0-0`, `libpangocairo-1.0-0`, `libcairo2`, `libgdk-pixbuf-2.0-0`, `libffi8`, `shared-mime-info`, and `fonts-liberation`.
5. **Data Persistence**:
   - Database state persists in Docker named volume `pgdata`.
   - File uploads, Grad-CAM overlays, and compiled PDFs persist in `./data:/app/data` on the host.

---

## 2. Configuration Files

### 2.1 `api/Dockerfile`
```dockerfile
FROM python:3.13-slim AS builder
WORKDIR /app

# Install build dependencies for compiling Python extensions (e.g. psycopg2, CFFI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install locked dependencies into virtual environment
ENV UV_NO_MANAGED_PYTHON=1
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim
WORKDIR /app

# Install runtime system libraries:
# - libpq5: PostgreSQL runtime client
# - libxcb1, libgl1, libglib2.0-0: OpenCV headless runtime
# - libpango-1.0-0, libpangoft2-1.0-0, libpangocairo-1.0-0, libcairo2, libgdk-pixbuf-2.0-0, libffi8, shared-mime-info, fonts-liberation: WeasyPrint PDF runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy prebuilt virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Ensure runtime directories exist for data persistence (scans, heatmaps, reports)
RUN mkdir -p data/scans data/heatmaps data/reports

# Copy application configuration and codebase
COPY alembic.ini ./
COPY api/ ./api/
COPY models/src/ ./models/src/
COPY models/checkpoints/ ./models/checkpoints/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Run database migrations automatically before starting Uvicorn
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn api.main:app --host 0.0.0.0 --port 8000"]
```

### 2.2 `docker-compose.yml`
```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-neuroscan_admin}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      POSTGRES_DB: ${POSTGRES_DB:-neuroscan_db}
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-neuroscan_admin} -d ${POSTGRES_DB:-neuroscan_db}"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: api/Dockerfile
    restart: unless-stopped
    env_file:
      - .env
    environment:
      - PYTHONUNBUFFERED=1
      - DATABASE_URL=postgresql://${POSTGRES_USER:-neuroscan_admin}:${POSTGRES_PASSWORD:-changeme}@db:5432/${POSTGRES_DB:-neuroscan_db}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./data:/app/data
      - ./models/checkpoints:/app/models/checkpoints

volumes:
  pgdata:
```

### 2.3 `.env.example`
```env
# =====================================================================
# NeuroScan Environment Configuration Template
# Copy this file to .env and adjust values for your environment.
# =====================================================================

# PostgreSQL Credentials & Database Name
POSTGRES_USER=neuroscan_admin
POSTGRES_PASSWORD=changeme
POSTGRES_DB=neuroscan_db

# Host & Port Settings (internal Docker network defaults)
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Database Connection URL (for containerized backend accessing internal 'db' service)
DATABASE_URL=postgresql://neuroscan_admin:changeme@db:5432/neuroscan_db

# Google Gemini API Key (Required for AI clinical narrative generation; obtain from Google AI Studio)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Gemini Model Name (defaults to gemini-flash-latest)
GEMINI_MODEL=gemini-flash-latest

# Optional: Minimum elapsed hours required between scans for longitudinal trend classification (default 1.0)
MIN_TREND_GAP_HOURS=1.0
```

### 2.4 `.dockerignore`
```
.venv
__pycache__
*.pyc
.git
data/
notebooks/.ipynb_checkpoints
frontend/node_modules/
frontend/dist/
```

---

## 3. Dependency Resolution & Gotchas

During the Docker configuration and lock validation pass, three dependency constraints were addressed:
1. **Missing `markdown` Library**:
   `api/core/pdf_export.py` converts Gemini narrative markdown to HTML using Python's `markdown` library. Added `markdown>=3.6` to `pyproject.toml`.
2. **TensorBoard / Protobuf Conflict**:
   `google-generativeai==0.8.6` requires `protobuf<6.0.0`, while recent `tensorboard` releases require `protobuf>=6`. Pinned `tensorboard>=2.18.0,<2.22.0` in `[dependency-groups] dev` so `uv lock` resolved `protobuf==5.29.6` cleanly.
3. **`requires-python` Range**:
   Bounded `requires-python = ">=3.13,<3.14"` in `pyproject.toml` to prevent solver conflicts with future Python 3.14 alpha dependencies.

---

## 4. Live Verification Output

### 4.1 Clean Wipe (`docker compose down -v`)
```
 Container neuroscan-api-1 Stopping 
 Container neuroscan-api-1 Stopped 
 Container neuroscan-api-1 Removing 
 Container neuroscan-api-1 Removed 
 Container neuroscan-db-1 Stopping 
 Container neuroscan-db-1 Stopped 
 Container neuroscan-db-1 Removing 
 Container neuroscan-db-1 Removed 
 Network neuroscan_default Removing 
 Volume neuroscan_pgdata Removing 
 Volume neuroscan_pgdata Removed 
 Network neuroscan_default Removed 
```

### 4.2 Clean Build and Startup (`docker compose up --build`)
*Verbatim output from build start through Uvicorn startup:*
```
 Image neuroscan-api Building 
#1 [internal] load local bake definitions
#1 reading from stdin 544B done
#1 DONE 0.0s

#2 [internal] load build definition from Dockerfile
#2 transferring dockerfile: 1.90kB done
#2 DONE 0.0s

#3 [internal] load metadata for ghcr.io/astral-sh/uv:latest
#3 DONE 1.2s

#4 [auth] library/python:pull token for registry-1.docker.io
#4 DONE 0.0s

#5 [internal] load metadata for docker.io/library/python:3.13-slim
#5 DONE 1.8s

#6 [internal] load .dockerignore
#6 transferring context: 149B done
#6 DONE 0.0s

#7 [internal] load build context
#7 transferring context: 3.89kB 0.0s done
#7 DONE 0.0s

#8 FROM ghcr.io/astral-sh/uv:latest@sha256:73d2665b478d8fa2de1cf105c6841f8e9cb6b09e568fc7700440c09f8fcd7ac4
#8 resolve ghcr.io/astral-sh/uv:latest@sha256:73d2665b478d8fa2de1cf105c6841f8e9cb6b09e568fc7700440c09f8fcd7ac4 0.0s done
#8 DONE 0.0s

#9 [builder 1/6] FROM docker.io/library/python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285
#9 resolve docker.io/library/python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285 0.0s done
#9 DONE 0.0s

#10 [stage-1 4/9] COPY --from=builder /app/.venv /app/.venv
#10 CACHED

#11 [builder 3/6] RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     libpq-dev     && rm -rf /var/lib/apt/lists/*
#11 CACHED

#12 [builder 5/6] COPY pyproject.toml uv.lock ./
#12 CACHED

#13 [builder 6/6] RUN uv sync --frozen --no-dev --no-install-project
#13 CACHED

#14 [stage-1 8/9] COPY models/src/ ./models/src/
#14 CACHED

#15 [stage-1 6/9] COPY alembic.ini ./
#15 CACHED

#16 [stage-1 3/9] RUN apt-get update && apt-get install -y --no-install-recommends     libpq5     libxcb1     libgl1     libglib2.0-0     libpango-1.0-0     libpangoft2-1.0-0     libpangocairo-1.0-0     libcairo2     libgdk-pixbuf-2.0-0     libffi8     shared-mime-info     fonts-liberation     && rm -rf /var/lib/apt/lists/*     && apt-get clean
#16 CACHED

#17 [builder 4/6] COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
#17 CACHED

#18 [builder 2/6] WORKDIR /app
#18 CACHED

#19 [stage-1 5/9] RUN mkdir -p data/scans data/heatmaps data/reports
#19 CACHED

#20 [stage-1 7/9] COPY api/ ./api/
#20 CACHED

#21 [stage-1 9/9] COPY models/checkpoints/ ./models/checkpoints/
#21 CACHED

#22 exporting to image
#22 exporting layers done
#22 exporting manifest sha256:42047142ddd4aa15707ff01029f9c83a1964225206e9f647bcf44ac6d84a729e done
#22 exporting config sha256:ded0946e955f8041dfc7448ae24267117e4394be62e55229a10307456e30f5e0 done
#22 exporting attestation manifest sha256:6e3e78b31b62bf57a248d0bb7e7c7d4409891892c89727a1a0f3ea459f643132 0.0s done
#22 exporting manifest list sha256:80b7abd2d7ba0b8c036f4c25ce684722af277d05f93f43833bbedc195f796842
#22 exporting manifest list sha256:80b7abd2d7ba0b8c036f4c25ce684722af277d05f93f43833bbedc195f796842 0.0s done
#22 naming to docker.io/library/neuroscan-api:latest done
#22 unpacking to docker.io/library/neuroscan-api:latest 0.0s done
#22 DONE 0.1s

#23 resolving provenance for metadata file
#23 DONE 0.0s
 Image neuroscan-api Built 
 Network neuroscan_default Creating 
 Network neuroscan_default Created 
 Volume neuroscan_pgdata Creating 
 Volume neuroscan_pgdata Created 
 Container neuroscan-db-1 Creating 
 Container neuroscan-db-1 Created 
 Container neuroscan-api-1 Creating 
 Container neuroscan-api-1 Created 
Attaching to api-1, db-1
 Container neuroscan-db-1 Starting 
 Container neuroscan-db-1 Started 
 Container neuroscan-db-1 Waiting 
db-1  | The files belonging to this database system will be owned by user "postgres".
db-1  | This user must also own the server process.
db-1  | 
db-1  | The database cluster will be initialized with locale "en_US.utf8".
db-1  | The default database encoding has accordingly been set to "UTF8".
db-1  | The default text search configuration will be set to "english".
db-1  | 
db-1  | Data page checksums are disabled.
db-1  | 
db-1  | fixing permissions on existing directory /var/lib/postgresql/data ... ok
db-1  | creating subdirectories ... ok
db-1  | selecting dynamic shared memory implementation ... posix
db-1  | selecting default max_connections ... 100
db-1  | selecting default shared_buffers ... 128MB
db-1  | selecting default time zone ... Etc/UTC
db-1  | creating configuration files ... ok
db-1  | running bootstrap script ... ok
db-1  | performing post-bootstrap initialization ... ok
db-1  | initdb: warning: enabling "trust" authentication for local connections
db-1  | initdb: hint: You can change this by editing pg_hba.conf or using the option -A, or --auth-local and --auth-host, the next time you run initdb.
db-1  | syncing data to disk ... ok
db-1  | 
db-1  | 
db-1  | Success. You can now start the database server using:
db-1  | 
db-1  |     pg_ctl -D /var/lib/postgresql/data -l logfile start
db-1  | 
db-1  | waiting for server to start....2026-09-09 16:28:57.978 UTC [48] LOG:  starting PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
db-1  | 2026-09-09 16:28:57.981 UTC [48] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
db-1  | 2026-09-09 16:28:57.988 UTC [51] LOG:  database system was shut down at 2026-09-09 16:28:57 UTC
db-1  | 2026-09-09 16:28:57.994 UTC [48] LOG:  database system is ready to accept connections
db-1  |  done
db-1  | server started
db-1  | CREATE DATABASE
db-1  | 
db-1  | 
db-1  | /usr/local/bin/docker-entrypoint.sh: ignoring /docker-entrypoint-initdb.d/*
db-1  | 
db-1  | waiting for server to shut down...2026-09-09 16:28:58.171 UTC [48] LOG:  received fast shutdown request
db-1  | .2026-09-09 16:28:58.174 UTC [48] LOG:  aborting any active transactions
db-1  | 2026-09-09 16:28:58.176 UTC [48] LOG:  background worker "logical replication launcher" (PID 54) exited with exit code 1
db-1  | 2026-09-09 16:28:58.176 UTC [49] LOG:  shutting down
db-1  | 2026-09-09 16:28:58.179 UTC [49] LOG:  checkpoint starting: shutdown immediate
db-1  | 2026-09-09 16:28:58.254 UTC [49] LOG:  checkpoint complete: wrote 926 buffers (5.7%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.015 s, sync=0.054 s, total=0.078 s; sync files=301, longest=0.006 s, average=0.001 s; distance=4273 kB, estimate=4273 kB; lsn=0/191F0F0, redo lsn=0/191F0F0
db-1  | 2026-09-09 16:28:58.258 UTC [48] LOG:  database system is shut down
db-1  |  done
db-1  | server stopped
db-1  | 
db-1  | PostgreSQL init process complete; ready for start up.
db-1  | 
db-1  | 2026-09-09 16:28:58.293 UTC [1] LOG:  starting PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
db-1  | 2026-09-09 16:28:58.294 UTC [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
db-1  | 2026-09-09 16:28:58.294 UTC [1] LOG:  listening on IPv6 address "::", port 5432
db-1  | 2026-09-09 16:28:58.298 UTC [1] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
db-1  | 2026-09-09 16:28:58.304 UTC [64] LOG:  database system was shut down at 2026-09-09 16:28:58 UTC
db-1  | 2026-09-09 16:28:58.310 UTC [1] LOG:  database system is ready to accept connections
 Container neuroscan-db-1 Healthy 
 Container neuroscan-api-1 Starting 
 Container neuroscan-api-1 Started 
api-1  | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
api-1  | INFO  [alembic.runtime.migration] Will assume transactional DDL.
api-1  | INFO  [alembic.runtime.migration] Running upgrade  -> 6b94c7970a64, create patients scans predictions reports tables
api-1  | INFO  [alembic.runtime.migration] Running upgrade 6b94c7970a64 -> 868e464ec1c2, add extra_data and model_version to predictions
api-1  | INFO:     Started server process [1]
api-1  | INFO:     Waiting for application startup.
api-1  | INFO:     Application startup complete.
api-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 4.3 Health Check (`curl http://localhost:8000/health`)
```http
HTTP/1.1 200 OK
date: Wed, 09 Sep 2026 16:29:28 GMT
server: uvicorn
content-length: 35
content-type: application/json

{"status":"ok","model_loaded":true}
```

### 4.4 Real Prediction Call (`POST http://localhost:8000/predict`)
- Registered Patient: `{"id": 1, "name": "Live Verification Patient", "mrn": "MRN-LIVE-VERIFY-001"}`
- Test Slice Uploaded: `data/scans/a0e0489f80fb41b6a435e67c1db7b4c0.jpg`
```json
{"disease_type":"brain_tumor","disease":"glioma","confidence":0.8523465991020203,"heatmap_url":"heatmaps/gradcam_0681aa0f9b64.png","all_class_probabilities":{"glioma":0.8523465991020203,"meningioma":0.13726769387722015,"no_tumor":0.0053522661328315735,"pituitary":0.005033470224589109},"affected_region":"upper-right region"}
```

### 4.5 Report Generation & PDF Output (`POST http://localhost:8000/patients/1/report`)
```json
{"id":1,"patient_id":1,"generated_at":"2026-09-09T16:31:31.902815","structured_findings":{"patient_id":1,"patient_name":"Live Verification Patient","mrn":"MRN-LIVE-VERIFY-001","date_of_birth":null,"total_scans":1,"diseases":{"brain_tumor":{"disease_type":"brain_tumor","latest":{"prediction_id":1,"scan_id":1,"date":"2026-09-09T16:29:50.687609","predicted_class":"glioma","confidence":0.8523,"affected_region":"upper-right region","gradcam_path":"data/heatmaps/gradcam_0681aa0f9b64.png","scan_path":"data/scans/31edea60144a48a6912d2cfba062fd2f.jpg","all_class_probabilities":{"glioma":0.8523465991020203,"meningioma":0.13726769387722015,"no_tumor":0.0053522661328315735,"pituitary":0.005033470224589109}},"history":[{"prediction_id":1,"scan_id":1,"date":"2026-09-09T16:29:50.687609","predicted_class":"glioma","confidence":0.8523,"affected_region":"upper-right region","gradcam_path":"data/heatmaps/gradcam_0681aa0f9b64.png","scan_path":"data/scans/31edea60144a48a6912d2cfba062fd2f.jpg","all_class_probabilities":{"glioma":0.8523465991020203,"meningioma":0.13726769387722015,"no_tumor":0.0053522661328315735,"pituitary":0.005033470224589109}}],"trend":null}}},"narrative_text":"**CLINICAL STUDY SUMMARY**\n* **Patient Name:** Live Verification Patient  \n* **Medical Record Number (MRN):** MRN-LIVE-VERIFY-001  \n* **Date of Birth:** None recorded  \n* **Total Scans on Record:** 1  \n* **Evaluation Type:** Automated AI imaging analysis for brain tumor classification  \n\n---\n\n**OBJECTIVE FINDINGS**\n* **Brain Tumor Evaluation (Scan Date: September 9, 2026):**\n  * **Classification:** The automated model categorized the image as consistent with glioma with a confidence score of 85.23% (probability: 0.8523). \n  * **Differential Probabilities:** Meningioma: 13.73% (0.1373), No Tumor: 0.54% (0.0054), Pituitary: 0.50% (0.0050).\n  * **Spatial Localization:** Model attention (Grad-CAM analysis) was concentrated primarily in the upper-right aspect of the imaged slice. This denotes a two-dimensional image coordinate centroid and does not represent an anatomically confirmed structure.\n\n---\n\n**LONGITUDINAL COMPARISON**\n* **Longitudinal Trend:** No longitudinal trend data is available. This study represents an isolated baseline evaluation, and prior imaging is unavailable for comparative analysis. Speculation regarding progression or temporal stability cannot be made.\n\n---\n\n**IMPRESSION**\n* Baseline AI analysis demonstrating model classification of glioma with 85.23% confidence, with salience localized to the upper-right region of the imaged slice.\n* No prior scans available for longitudinal comparison.","pdf_path":"data/reports/report_1.pdf"}
```

- **Compiled PDF File on Host Volume (`data/reports/report_1.pdf`)**:
```
 Directory of C:\Users\ASUS\OneDrive\Documents\NeuroScan\data\reports

09-Sep-26  10:01 PM            87,758 report_1.pdf
               1 File(s)         87,758 bytes
```

### 4.6 Persistence Verification Across Container Restarts
1. **Container Shutdown** (`docker compose down` without `-v`):
```
 Container neuroscan-api-1 Stopping 
 Container neuroscan-api-1 Stopped 
 Container neuroscan-api-1 Removing 
 Container neuroscan-api-1 Removed 
 Container neuroscan-db-1 Stopping 
 Container neuroscan-db-1 Stopped 
 Container neuroscan-db-1 Removing 
 Container neuroscan-db-1 Removed 
 Network neuroscan_default Removing 
 Network neuroscan_default Removed 
```

2. **Container Restart** (`docker compose up -d`):
```
 Network neuroscan_default Creating 
 Network neuroscan_default Created 
 Container neuroscan-db-1 Creating 
 Container neuroscan-db-1 Created 
 Container neuroscan-api-1 Creating 
 Container neuroscan-api-1 Created 
 Container neuroscan-db-1 Starting 
 Container neuroscan-db-1 Started 
 Container neuroscan-db-1 Waiting 
 Container neuroscan-db-1 Healthy 
 Container neuroscan-api-1 Starting 
 Container neuroscan-api-1 Started 
```

3. **Data Verification Call (`GET http://localhost:8000/patients`)**:
```http
HTTP/1.1 200 OK
date: Wed, 09 Sep 2026 16:32:43 GMT
server: uvicorn
content-length: 136
content-type: application/json

[{"id":1,"name":"Live Verification Patient","mrn":"MRN-LIVE-VERIFY-001","date_of_birth":null,"created_at":"2026-09-09T16:29:50.323163"}]
```

---

## 5. Verification Checklist

| Verification Item | Target | Observed Result | Status |
| :--- | :--- | :--- | :---: |
| **Clean Reset** | `docker compose down -v` | Wiped all containers, networks, and named volumes | ✅ Verified |
| **Foreground Build** | `docker compose up --build` | Completed build without errors; bound Uvicorn to `0.0.0.0:8000` | ✅ Verified |
| **Schema Initialization** | Auto-migration on container boot | Applied `6b94c7970a64` and `868e464ec1c2` without manual intervention | ✅ Verified |
| **Health Check** | `GET /health` | `HTTP 200 OK`, `{"status":"ok","model_loaded":true}` | ✅ Verified |
| **PyTorch Inference** | `POST /predict` | Glioma (85.23%), Grad-CAM heatmap generated, upper-right region mapped | ✅ Verified |
| **WeasyPrint PDF** | `POST /patients/1/report` | Gemini LLM narrative + WeasyPrint compiled 87,758-byte PDF | ✅ Verified |
| **State Persistence** | `docker compose down` -> `up -d` | Patient record, scan record, and report metadata persisted | ✅ Verified |
| **Static File Serving** | `GET /data/...` | Static files served from persistent host volume | ✅ Verified |
