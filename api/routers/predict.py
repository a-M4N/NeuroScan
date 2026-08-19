"""
POST /predict — run tumor classification on an uploaded brain MRI scan.

Flow:
  1. Save the uploaded file to a temp path
  2. Preprocess it into a model-ready tensor (api/core/preprocessing.py)
  3. Run inference -> class + confidence + full probability distribution
  4. If a tumor is detected, generate a Grad-CAM heatmap (api/core/gradcam.py)
  5. Persist Scan + Prediction records to the DB
  6. Return a PredictionResponse
"""

import logging
import shutil
import tempfile
import uuid
from pathlib import Path

import torch
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.core import model_loader
from api.core.gradcam import generate_heatmap
from api.core.preprocessing import get_rgb_array_for_gradcam, preprocess
from api.db.database import get_db
from api.db.models import Patient, Prediction, Scan
from api.schemas.predict import PredictErrorResponse, PredictionResponse
from models.src.model import CLASS_LABELS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["predict"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".nii", ".gz", ".dcm"}

DISEASE_TYPE = "brain_tumor"  # only classifier active as of Phase 3/4


@router.post(
    "",
    response_model=PredictionResponse,
    responses={400: {"model": PredictErrorResponse}, 500: {"model": PredictErrorResponse}},
)
async def predict(
    file: UploadFile = File(..., description="Brain MRI scan: jpg/png, .nii/.nii.gz, or .dcm"),
    patient_id: str = Form(..., description="ID of the patient this scan belongs to"),
    slice_index: int | None = Form(
        default=None,
        description="Axial slice to analyze for NIfTI/DICOM volumes. Defaults to middle slice.",
    ),
    db: Session = Depends(get_db),
):
    # --- 1. Validate file type early ---
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS and not file.filename.lower().endswith(".nii.gz"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Expected one of: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # --- 2. Resolve patient (patient_id here is the MRN/external identifier) ---
    patient = db.query(Patient).filter(Patient.mrn == patient_id).first()
    if patient is None:
        raise HTTPException(
            status_code=404,
            detail=f"Patient with mrn '{patient_id}' not found. Create the patient first via POST /patients.",
        )

    # --- 3. Save upload to a temp path ---
    tmp_dir = Path(tempfile.gettempdir()) / "neuroscan_uploads"
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}{suffix if suffix else Path(file.filename).suffix}"

    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        logger.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")
    finally:
        file.file.close()

    # --- 4. Persist a permanent copy of the scan (temp dir gets wiped on cleanup) ---
    scans_dir = Path("data/scans")
    scans_dir.mkdir(parents=True, exist_ok=True)
    permanent_scan_path = scans_dir / tmp_path.name
    shutil.copy(tmp_path, permanent_scan_path)

    # --- 5. Run preprocessing + inference ---
    try:
        model = model_loader.get_model()
        cam = model_loader.get_cam()
        device = model_loader.get_device()

        input_tensor = preprocess(tmp_path, slice_index=slice_index).to(device)

        with torch.no_grad():
            output = model(input_tensor)
            probabilities = torch.softmax(output, dim=1)[0]
            pred_idx = int(probabilities.argmax().item())
            confidence = float(probabilities[pred_idx].item())

        all_class_probabilities = {
            CLASS_LABELS[i]: float(probabilities[i].item()) for i in range(len(CLASS_LABELS))
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        logger.exception("Model not ready")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Inference failed")
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")

    # --- 6. Grad-CAM (skip for no_tumor) ---
    heatmap_url = None
    predicted_label = CLASS_LABELS[pred_idx]

    if predicted_label != "no_tumor":
        try:
            rgb_img = get_rgb_array_for_gradcam(tmp_path, slice_index=slice_index)
            result = generate_heatmap(cam, input_tensor, rgb_img, pred_idx)
            heatmap_url = result["heatmap_path"]
        except Exception:
            logger.exception("Grad-CAM generation failed; returning prediction without heatmap")

    # --- 7. Cleanup temp upload ---
    try:
        tmp_path.unlink(missing_ok=True)
    except Exception:
        logger.warning(f"Failed to clean up temp file {tmp_path}")

    # --- 8. Persist Scan + Prediction records ---
    try:
        scan = Scan(
            patient_id=patient.id,
            file_path=str(permanent_scan_path),
            modality=suffix.lstrip("."),
        )
        db.add(scan)
        db.flush()  # get scan.id without committing yet

        prediction = Prediction(
            scan_id=scan.id,
            disease_type=DISEASE_TYPE,
            predicted_class=predicted_label,
            confidence=confidence,
            gradcam_path=heatmap_url,
        )
        db.add(prediction)
        db.commit()
        db.refresh(prediction)
    except Exception:
        db.rollback()
        logger.exception("Failed to persist scan/prediction records")
        # Don't fail the whole request just because persistence failed —
        # the classification itself succeeded. Log loudly and continue.

    return PredictionResponse(
        disease=predicted_label,
        confidence=confidence,
        heatmap_url=heatmap_url,
        all_class_probabilities=all_class_probabilities,
    )