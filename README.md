# NeuroScan — AI-Based Brain MRI Disease Detection & Reporting System

> **Purpose of this document:** This README gives any AI coding agent (Claude Code, Antigravity, Cursor, Copilot, etc.) or developer full context on NeuroScan's history, architecture, verified implementation, and conventions — without needing to re-derive anything or ask questions already resolved. Read this in full before modifying the codebase.

---

## 1. Project Overview

**NeuroScan** is a full-stack medical AI application that analyzes brain MRI scans to detect neurological conditions, generates visual explainability (Grad-CAM saliency heatmaps with parenchyma masking), derives 2D positional lesion localizations, aggregates longitudinal patient findings across time, and compiles complete diagnostic PDF reports with LLM-synthesized radiologic narratives.

### Original Vision vs. Current Implementation
* **Original 5-Disease Vision (Initial Project Spec):**
  1. Brain Tumor (Glioma, Meningioma, Pituitary Adenoma, Healthy control)
  2. Alzheimer's Disease / Dementia (Multi-class staging: Non-demented, Very Mild, Mild, Moderate)
  3. Stroke — Ischemic lesion detection
  4. Multiple Sclerosis — White matter lesion detection
  5. Hydrocephalus — Ventricular enlargement detection
* **Currently Implemented (Phases 0–6 Complete):** 
  * **2 of 5 diseases:** Brain Tumor and Alzheimer's Disease.
  * The system is deliberately architected around a central model registry (`models/src/disease_configs.py`). Integrating diseases #3, #4, and #5 requires adding configuration entries, checkpoints, and class definitions—without rewriting the routing, persistence, Grad-CAM, or reporting pipelines.

### Core Design Philosophy
1. **Explainable Per-Disease Models:** Rather than a monolithic black-box classifier, each pathology is evaluated by a dedicated, validated PyTorch model paired with disease-specific Grad-CAM interpretability.
2. **LLM as a Clinical Scribe, Not a Diagnostician:** Generative AI (Google Gemini Flash) is strictly restricted to phrasing and structuring verified algorithmic findings. It **never** predicts diagnoses, invents conditions, overrides confidence scores, or prescribes clinical treatments/biopsies.
3. **Genuine Deliverables Beyond JSON:** NeuroScan produces tangible clinical deliverables: masked Grad-CAM overlays, interval-aware longitudinal comparison tables, and downloadable, print-ready PDF diagnostic reports.

---

## 2. Tech Stack (As Actually Implemented)

* **Backend Web Framework:** FastAPI (Python 3.11 / 3.13)
* **Database & Persistence:** PostgreSQL 16 (running via Docker Compose), SQLAlchemy 2.0 ORM, and Alembic database migrations.
* **Deep Learning Framework:** PyTorch with transfer-learning backbones (EfficientNet-B0) via `timm`.
* **Explainability (Grad-CAM):** `grad-cam` (PyPI package targeting `conv_head` layers).
* **Scientific Image Processing:**
  * `scipy` (`scipy.ndimage` for connected-component analysis and binary erosion background masking).
  * `Pillow` & `torchvision` (slice transformations and ImageNet normalization).
  * `NiBabel` (NIfTI `.nii`/`.nii.gz` 3D volume slice extraction).
  * `pydicom` (DICOM `.dcm` slice extraction).
* **Document Compilation & Templating:**
  * `Jinja2` (HTML report templating).
  * `WeasyPrint` (HTML/CSS to PDF compilation, running against GTK+ 3 native C libraries).
  * `markdown` (Python library converting structured LLM narrative text into clean HTML).
  * `pypdfium2` (PDF rendering and inspection).
* **Large Language Model:** Google Gemini Flash (`google-generativeai` SDK, free tier via Google AI Studio).
* **Package Management:** `uv` (fast, deterministic virtualenv and dependency management).
* **Containerization:** Docker & Docker Compose.

### Aspirational Spec vs. Pragmatic Implementation Decisions
* **LLM Engine:** The original spec proposed the Anthropic Claude API. Google Gemini Flash was adopted instead due to Google AI Studio's free-tier availability, eliminating cost barriers while maintaining strict medical scribe adherence via prompt engineering.
* **Medical Preprocessing Toolkits:** MONAI, SimpleITK, and ANTsPy were initially proposed for stereotaxic atlas registration and affine skull stripping. They were deferred to keep the deployment lightweight and pure-Python. Coarse background masking is performed using `scipy.ndimage` connected components, and region mapping uses explicit 2D image coordinate bounds rather than unverified anatomical claims.

---

## 3. Project Structure

```
NeuroScan/
├── api/
│   ├── core/
│   │   ├── gradcam.py            # Grad-CAM generation + connected-component/erosion background masking
│   │   ├── model_loader.py       # Lifespan model & GradCAM preloader; caches in-memory PyTorch weights
│   │   ├── narrative.py          # Google Gemini Flash clinical narrative synthesis with strict guardrails
│   │   ├── pdf_export.py         # Jinja2 + WeasyPrint PDF report compilation engine with non-fatal isolation
│   │   ├── preprocessing.py      # Format-agnostic image loading (JPG/PNG/NIfTI/DICOM) and normalization
│   │   ├── region_mapping.py     # Coarse 2D image-coordinate position mapping from Grad-CAM centroid
│   │   └── report_builder.py     # Aggregates scan history, structured findings, and interval-aware trends
│   ├── db/
│   │   ├── database.py           # SQLAlchemy engine/session setup; forces load_dotenv(override=True)
│   │   ├── models.py             # Declarative ORM models: Patient, Scan, Prediction, Report
│   │   └── migrations/           # Alembic schema migrations (e.g. extra_data, model_version)
│   ├── routers/
│   │   ├── patients.py           # Patient CRUD, scan history, report generation, and PDF streaming/regen
│   │   └── predict.py            # POST /predict — unified multi-disease inference endpoint
│   ├── schemas/
│   │   ├── predict.py            # Pydantic validation models for /predict requests and responses
│   │   └── report.py             # Pydantic models for structured findings, longitudinal trends, and reports
│   ├── templates/
│   │   └── report_template.html  # Jinja2 clinical report template with @page rules, imaging grid, and disclaimers
│   ├── Dockerfile                # API container definition with PYTHONUNBUFFERED=1
│   └── main.py                   # FastAPI application factory, CORS setup, and lifespan context
├── data/
│   ├── heatmaps/                 # Stored Grad-CAM PNG overlays
│   ├── reports/                  # Generated clinical PDF reports (report_{id}.pdf)
│   │   └── previews/             # Rendered PNG page previews for visual inspection
│   └── scans/                    # Stored raw patient MRI uploads
├── models/
│   ├── checkpoints/
│   │   ├── tumor_classifier_brisc2025.pth # Fine-tuned 4-class EfficientNet-B0 for Brain Tumor
│   │   └── alzheimers_effnet_b0.pth       # Fine-tuned 4-class EfficientNet-B0 for Alzheimer's
│   └── src/
│       ├── dataset.py            # PyTorch datasets with patient-level leakage-free partitioning
│       ├── disease_configs.py    # DISEASE_CONFIGS registry — single source of truth for disease metadata
│       ├── model.py              # EfficientNet-B0 architecture construction and checkpoint loader
│       └── train.py              # Training script supporting AMP and WeightedRandomSampler
├── notebooks/
│   └── 01_tumor_classifier.ipynb # Prototyping and validation notebook
├── scripts/
│   └── verify_phase6_pdf.py      # Automated end-to-end verification script for reports, trends, and PDFs
├── alembic.ini                   # Alembic environment and database URL configuration
├── docker-compose.yml            # Docker services: PostgreSQL (host port 5433) and NeuroScan API
├── pyproject.toml                # UV-managed Python project dependencies
├── README.md                     # Comprehensive technical documentation and developer reference
├── REPORT_GENERATION_PHASE_COMPLETE_DETAILS.md # Architectural report generation walkthrough
└── uv.lock                       # Deterministic dependency lockfile
```

---

## 4. Build History — Phase by Phase

### Phase 0: Project Setup & Infrastructure
* **Deliverables:** Configured Python virtual environment using `uv`, initialized Docker Compose with PostgreSQL 16, created base directory layout, established Alembic migration environment, and standardized dependencies in `pyproject.toml`.

### Phase 1: Brain Tumor Classifier
* **Deliverables:** Fine-tuned an EfficientNet-B0 backbone on the Kaggle **BRISC2025** Brain MRI dataset across 4 classes: `glioma`, `meningioma`, `no_tumor`, and `pituitary`.
* **Performance:** Achieved ~98% test accuracy on held-out test data. Checkpoint saved to `models/checkpoints/tumor_classifier_brisc2025.pth`.
* **Documented Limitation:** Early models occasionally misclassified meningioma as `no_tumor` due to Grad-CAM shortcut learning along the skull rim (resolved later in Phase 6b).

### Phase 2: Grad-CAM Explainability
* **Deliverables:** Integrated `grad-cam` targeting the `conv_head` layer of EfficientNet-B0. Generates normalized RGB colormap overlays composited on the resized MRI slice.
* **Core Invariant:** Preprocessing in `api/core/preprocessing.py` strictly mirrors the training transformation pipeline (resize to 224×224, normalize with ImageNet mean `[0.485, 0.456, 0.406]` and std `[0.229, 0.224, 0.225]`). Any mismatch silently degrades model inference.
* **Negative Class Bypass:** For negative/healthy classes (`no_tumor`, `non_demented`), Grad-CAM generation is bypassed to prevent generating misleading visual noise on healthy scans.

### Phase 3: FastAPI `/predict` Endpoint
* **Deliverables:** Built the primary asynchronous REST endpoint `POST /predict`.
* **Multi-Format Ingestion:** Added support for JPEG, PNG, NIfTI (`.nii`, `.nii.gz`), and DICOM (`.dcm`). Implemented axial slice extraction (middle slice by default, or configurable `slice_index`).

### Phase 4: Database Persistence & Patient History
* **Deliverables:** Established relational schema using SQLAlchemy ORM:
  * `Patient`: Identifiers, name, MRN, date of birth.
  * `Scan`: File paths, modality, upload timestamps.
  * `Prediction`: Disease type, predicted class, confidence, Grad-CAM path, model version, and auxiliary JSON data.
  * `Report`: Patient FK, narrative text, generated PDF path, and generation timestamp.
* **Key Design Decision (Non-Fatal Persistence):** Database write failures do **not** fail the HTTP request. If PostgreSQL encounters a transient write error, the classification and heatmap are still returned to the client, while the database error is logged via `logger.exception`.

### Phase 5: Multi-Disease Generalization & Alzheimer's Classifier
* **Deliverables:** Refactored the architecture to be disease-agnostic:
  * Created `models/src/disease_configs.py` exposing `DISEASE_CONFIGS`, standardizing class labels, checkpoint paths, negative classes, and feature flags.
  * Implemented the Model Registry pattern in `api/core/model_loader.py` to preload weights and Grad-CAM hooks during FastAPI startup (`lifespan`).
* **Alzheimer's Classifier:** Fine-tuned EfficientNet-B0 on the 4-class **OASIS** dataset (`non_demented`, `very_mild_demented`, `mild_demented`, `moderate_demented`).
* **Deliberately Accepted Limitation (`moderate_demented` 0% recall):**
  * In the patient-disjoint OASIS training set, only **1 single patient** represents the `moderate_demented` class. The network cannot generalize moderate dementia features from a single anatomy.
  * Rather than over-fitting with artificial synthetic augmentation or leaking slices across train/test splits, this constraint was accepted and documented as a data scarcity limitation.

---

### Phase 6: Explainability Refinement, Structured Reporting & PDF Export

Phase 6 completed the end-to-end diagnostic reporting system. Every component was independently verified against raw files, database records, and visual outputs:

#### 6a. Positional Region Mapping (`affected_region`)
* **Objective:** Ground focal lesion visual attention in a standardized 2D position label.
* **Implementation:** `api/core/region_mapping.py` computes the activation-weighted centroid $(c_x, c_y)$ of the thresholded Grad-CAM heatmap and maps it into a 2D position grid:
  * Vertical: `upper` ($<0.38$), `central` ($0.38–0.62$), `lower` ($>0.62$).
  * Horizontal: `left` ($<0.38$), `central` ($0.38–0.62$), `right` ($>0.62$).
  * Produces labels such as `"upper-left region"`, `"central region"`, `"lower-right region"`.
* **Critical Architectural Invariant:** The preprocessing pipeline does not perform stereotaxic registration or DICOM orientation tag parsing. Therefore, the system **strictly avoids anatomical claims** (e.g., naming lobes, gyri, or hemispheres). It is explicitly treated as a 2D image-coordinate heuristic.
* **Gating:** Controlled per-disease via `DiseaseConfig.region_mapping_enabled`. Set to `True` for `brain_tumor` (focal lesions), and `False` for `alzheimers` (diffuse brain-wide neurodegeneration).

#### 6b. Grad-CAM Background Masking Fix
* **Problem:** Raw Grad-CAM heatmaps frequently displayed intense activations around the outer skull perimeter and into the empty black space outside the head.
* **Dead End Attempt (Empirically Rejected):** Raw pixel brightness thresholding was attempted. Raising the brightness cutoff from 0.15 to 0.25 did not remove the skull-edge ring (bone and scalp were bright enough to pass) and damaged internal tumor signal by clipping dark brain structures (ventricles and sulci).
* **Working Solution (Connected Components + Erosion):** Implemented `_mask_background` in `api/core/gradcam.py`:
  1. Threshold image brightness at `0.15` to identify all illuminated regions.
  2. Use `scipy.ndimage.label` to isolate the **largest connected component** (the patient's head), discarding background flecks.
  3. Apply `scipy.ndimage.binary_erosion` to shrink the head mask inward by `erosion_pixels` (standardized to **12**), cleanly shearing off skull/scalp rim artifacts.
  4. Multiply raw `grayscale_cam` by this eroded mask before applying colormap overlays or calculating region centroids.

#### 6c. Structured Findings Builder & Gemini Clinical Narrative
* **Report Builder (`api/core/report_builder.py`):** Aggregates patient demographics, current predictions, and prior studies per disease.
* **Longitudinal Trend Safety Fix (`insufficient_interval`):**
  * **The Risk:** Test/QA uploads performed seconds apart previously triggered false "new finding" or "progression" claims.
  * **The Fix:** If two scans of the same pathology occur less than **1 hour** apart, the system assigns `trend = "insufficient_interval"`.
  * For intervals $> 1\text{ hour}$, it computes real trajectories: `new_finding`, `resolved`, `stable`, `changed` (tumors) or `progression`, `regression`, `stable` (dementia).
* **Gemini Clinical Narrative (`api/core/narrative.py`):**
  * Uses Google Gemini Flash with strict medical scribe instructions.
  * **Strict Invariants:** Rephrasing only; no diagnoses beyond the data; position-based localization hedges (mandates stating model attention was within the image slice without inferring lobes); no treatment, biopsy, or imaging recommendations.
  * **Non-Fatal Fallback:** If `GEMINI_API_KEY` is missing or quota is exhausted, the report is created with a clean fallback message without failing the request.

#### 6d. PDF Report Export (Jinja2 + WeasyPrint)
* **Template (`api/templates/report_template.html`):** Clinical layout using CSS `@page` rules (A4, 16mm margins), page counters (`counter(page)` / `counter(pages)`), patient demographic header, side-by-side MRI slice and Grad-CAM imaging grid, longitudinal trend card, rendered markdown narrative, and regulatory disclaimers.
* **Generator (`api/core/pdf_export.py`):** Resolves image paths to absolute `file:///` URIs, renders HTML, compiles PDF via WeasyPrint into `data/reports/report_{id}.pdf`, and records `pdf_path` in PostgreSQL.
* **Endpoints (`api/routers/patients.py`):**
  * `POST /patients/{id}/report`: Compiles report and auto-triggers PDF generation.
  * `GET /patients/{id}/reports/{report_id}`: Retrieves report metadata with `pdf_path`.
  * `GET /patients/{id}/reports/{report_id}/pdf`: Streams the PDF file (`application/pdf`, attachment header).
  * `POST /patients/{id}/reports/{report_id}/pdf`: On-demand regeneration endpoint.

---

## 5. Environment & Local Dev Setup — Gotchas

Documented environment-specific behaviors to prevent re-investigating known issues:

### 1. Windows PostgreSQL Port Conflict (Port 5432 vs. 5433)
* **Symptom:** Inexplicable password authentication failures connecting to PostgreSQL.
* **Cause:** A native Windows PostgreSQL service was listening on port 5432, intercepting TCP connections meant for the Docker container.
* **Resolution:** Docker PostgreSQL host port is remapped to **`5433`** (`"5433:5432"` in `docker-compose.yml`). The `.env` database connection must always specify `localhost:5433`:
  ```bash
  DATABASE_URL=postgresql://neuroscan:neuroscan_dev@localhost:5433/neuroscan
  ```

### 2. Stale Shell Environment Variables
* **Symptom:** Python scripts connecting to an unexpected database port despite `.env` being correct.
* **Cause:** PowerShell session variables (`$env:DATABASE_URL`) silently shadow `.env` definitions.
* **Resolution:** `api/db/database.py` enforces `load_dotenv(override=True)`. Always verify with `echo $env:DATABASE_URL` if connection behavior seems erratic.

### 3. Dual API Processes (Docker vs. Local Uvicorn)
* **Symptom:** Code modifications not reflecting during API testing.
* **Cause:** The Docker container `neuroscan-api-1` and a local `uvicorn api.main:app --reload` process can run concurrently on port 8000.
* **Resolution:** During active local development, stop the Docker API container (`docker stop neuroscan-api-1`) and run uvicorn locally.

### 4. WeasyPrint Native C Dependencies on Windows (GTK+ 3)
* **Symptom:** `cannot load library 'gobject-2.0-0'` or `cairo` OSError when importing WeasyPrint.
* **Resolution:** Install the GTK+ 3 64-bit runtime:
  ```powershell
  winget install tschoonj.GTKForWindows
  ```
  `api/core/pdf_export.py` programmatically registers the runtime DLL folder:
  ```python
  if sys.platform == "win32":
      gtk_bin = r"C:\Program Files\GTK3-Runtime Win64\bin"
      if os.path.exists(gtk_bin):
          os.add_dll_directory(gtk_bin)
  ```

### 5. Windows File Locking During PDF Regeneration (`[Errno 13]`)
* **Symptom:** `[Errno 13] Permission denied: 'data\reports\report_X.pdf'`.
* **Cause:** On Windows, if a PDF file is open in Adobe Acrobat, Edge, or a browser viewer, the operating system places an exclusive write lock on the file.
* **Resolution:** Close the PDF in external viewers before triggering re-generation. The PDF exporter handles this non-fatally, logging a warning rather than crashing.

### 6. Package Management Conventions
* Always use `uv add <package>` or `uv pip install <package>` within `.venv`. Avoid raw global `pip install` to ensure `pyproject.toml` and `uv.lock` stay synchronized.

---

## 6. Key Engineering Principles Established

1. **Verify Actual Code and Raw Output Before Making Claims:**
   * Never describe what was assumed or intended; inspect actual file contents. Twice in this project, written summaries drifted from reality (claiming anatomical lobe labeling and biopsy recommendations when the code strictly forbade both).
   * Verify vision and document outputs directly: open and inspect actual rendered PDFs (`data/reports/`), check database rows via SQL, and examine generated Grad-CAM images.
2. **Synchronize Multi-File Signature Changes in a Single Pass:**
   * When modifying a function signature or parameter default (e.g. `erosion_pixels` 11 vs. 12, or adding parameters to `generate_heatmap`), update the definition, call sites, and Form defaults in the same pass.
3. **Accept Documented Limitations Over Endless Tuning:**
   * When data or architecture cannot support a feature cleanly (e.g., `moderate_demented` 0% recall due to single-patient training data; positional rather than anatomical region mapping due to lack of stereotaxic registration), clearly document the limitation rather than over-engineering fragile heuristics.
4. **Fail Non-Fatally for Auxiliary Services:**
   * Primary inference and reporting must remain resilient. If database persistence, Grad-CAM generation, Gemini narrative synthesis, or WeasyPrint PDF compilation encounters an exception, log the error loudly and return the core data (with `null` fields) rather than returning a 500 error to the client.
5. **Gate Disease Behaviors in `DiseaseConfig`:**
   * Never hardcode disease-specific conditionals in routers or services. Add declarative flags to `DiseaseConfig` (e.g., `region_mapping_enabled`, `negative_class`, `severity_order`).
6. **Don't Claim More Than the Pipeline Can Support:**
   * Keep localization language strictly coordinate-based unless real 3D stereotaxic registration is implemented. Enforce interval thresholds (`insufficient_interval`) so rapid QA uploads are not misreported as disease progression.

---

## 7. Current State Summary

### Complete & Fully Verified (Phases 0–6)
* **Phase 0–1:** EfficientNet-B0 Brain Tumor classifier (`glioma`, `meningioma`, `no_tumor`, `pituitary`) with ~98% test accuracy.
* **Phase 2:** Disease-agnostic Grad-CAM generation targeting `conv_head`.
* **Phase 3:** Unified FastAPI `/predict` supporting JPG, PNG, NIfTI, and DICOM formats.
* **Phase 4:** PostgreSQL persistence with SQLAlchemy models (`Patient`, `Scan`, `Prediction`, `Report`).
* **Phase 5:** Multi-disease registry and 4-class Alzheimer's disease classifier (`non_demented`, `very_mild_demented`, `mild_demented`, `moderate_demented`).
* **Phase 6a:** 2D positional region mapping (`affected_region`) with spatial bounds.
* **Phase 6b:** Connected-component and binary erosion background masking (`erosion_pixels=12`) eliminating skull rim and background air artifacts.
* **Phase 6c:** Structured findings builder, interval-aware longitudinal trend tracking ($<1\text{ hr}$ safety guard), and Google Gemini Flash radiologic narrative synthesis with non-fatal fallback.
* **Phase 6d:** Clinical PDF report export using Jinja2 and WeasyPrint, verified across baseline, multi-disease, longitudinal, and positive Alzheimer's test cases.

### Not Yet Started
* **Frontend:** Modern responsive web interface (React/Vite/Next.js).
* **Additional Disease Models:** Classifiers for Stroke, Multiple Sclerosis, and Hydrocephalus.
* **Asynchronous Task Queue:** Celery/Redis for background batch inference and heavy volume processing.
* **Production Deployment:** Cloud container orchestration, HTTPS reverse proxy, and monitoring.

---

## 8. Immediate Next Steps (Options to Pick From)

1. **Option A — Frontend Web Application:**
   * Develop an interactive clinician dashboard (React/Vite) for uploading MRI scans (2D/3D), viewing side-by-side Grad-CAM heatmaps, tracking patient timelines, and previewing/downloading PDF reports directly.
2. **Option B — Expand Disease Models (Disease #3: Stroke):**
   * Source an ischemic stroke MRI dataset, fine-tune an EfficientNet classifier, configure `DiseaseConfig` in `models/src/disease_configs.py`, and register the checkpoint without modifying router code.
3. **Option C — Asynchronous Task Processing & 3D Volumetric Benchmarking:**
   * Introduce Redis and Celery to handle large 3D NIfTI/DICOM volume processing asynchronously, allowing background job status polling for multi-slice scans.
