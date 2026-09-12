"""
POST /predict — run disease classification on an uploaded brain MRI scan.

Unified across all disease types (Phase 5+): the caller specifies
disease_type, and the model/Grad-CAM/class-labels used are resolved
from DISEASE_CONFIGS via the model registry. Adding a new disease later
means adding an entry to DISEASE_CONFIGS — this file doesn't change.

Flow:
  1. Validate disease_type against DISEASE_CONFIGS
  2. Save the uploaded file to a temp path
  3. Preprocess it into a model-ready tensor (api/core/preprocessing.py)
  4. Run inference -> class + confidence + full probability distribution
  5. If the predicted class isn't that disease's negative class, generate
     a Grad-CAM heatmap (api/core/gradcam.py)
  6. Persist Scan + Prediction records to the DB
  7. Return a PredictionResponse
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
from models.src.disease_configs import DISEASE_CONFIGS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["predict"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".nii", ".gz", ".dcm"}


@router.post(
    "",
    response_model=PredictionResponse,
    responses={400: {"model": PredictErrorResponse}, 500: {"model": PredictErrorResponse}},
)
async def predict(
    file: UploadFile = File(..., description="Brain MRI scan: jpg/png, .nii/.nii.gz, or .dcm"),
    patient_id: str = Form(..., description="ID of the patient this scan belongs to"),
    disease_type: str = Form(
        ..., description=f"One of: {sorted(DISEASE_CONFIGS.keys())}"
    ),
    slice_index: int | None = Form(
        default=None,
        description="Axial slice to analyze for NIfTI/DICOM volumes. Defaults to middle slice.",
    ),
    gradcam_brightness_threshold: float = Form(
        default=0.15,
        description=(
        "Experimental: pixels below this brightness (0-1) in the MRI slice are "
        "masked out of the Grad-CAM before overlay/region derivation, to reduce "
        "background/skull-edge activation. Tune per scan if heatmaps look off."
    ),
    ),
    gradcam_erosion_pixels: int = Form(
        default=12,
        description=(
            "Experimental: how many pixels to erode inward from the detected "
            "head boundary before Grad-CAM overlay/region derivation, to "
            "exclude skull/scalp-edge activation. Higher = more aggressive."
        ),
),
    db: Session = Depends(get_db),
):
    # --- 0. Validate disease_type against the live registry ---
    if disease_type not in DISEASE_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown disease_type '{disease_type}'. Expected one of: {sorted(DISEASE_CONFIGS.keys())}",
        )
    cfg = DISEASE_CONFIGS[disease_type]

    # --- 1. Validate file type early ---
    # Path.suffix only captures the LAST extension (.gz for "scan.nii.gz"),
    # so compound extensions need explicit handling — both here and again
    # in step 3 when constructing the temp filename, since nibabel needs
    # the full ".nii.gz" to correctly infer gzipped-NIfTI format.
    original_name_lower = file.filename.lower()
    if original_name_lower.endswith(".nii.gz"):
        suffix = ".nii.gz"
    else:
        suffix = Path(file.filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS and suffix != ".nii.gz":
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
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}{suffix}"  # suffix already correctly
                                                          # includes ".nii.gz" when applicable

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

    # --- 5. Run preprocessing + inference (model/cam resolved by disease_type) ---
    try:
        model = model_loader.get_model(disease_type)
        cam = model_loader.get_cam(disease_type)
        device = model_loader.get_device()

        input_tensor = preprocess(tmp_path, slice_index=slice_index).to(device)

        with torch.no_grad():
            output = model(input_tensor)
            probabilities = torch.softmax(output, dim=1)[0]
            pred_idx = int(probabilities.argmax().item())
            confidence = float(probabilities[pred_idx].item())

        all_class_probabilities = {
            cfg.class_labels[i]: float(probabilities[i].item()) for i in range(len(cfg.class_labels))
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

        # --- 6. Grad-CAM (skip for this disease's negative class) ---
    heatmap_url = None
    heatmap_fs_path = None
    affected_region = None
    predicted_label = cfg.class_labels[pred_idx]

    if cfg.negative_class is None or predicted_label != cfg.negative_class:
        try:
            rgb_img = get_rgb_array_for_gradcam(tmp_path, slice_index=slice_index)
            negative_idx = (
                cfg.class_labels.index(cfg.negative_class)
                if cfg.negative_class is not None else None
            )

            result = generate_heatmap(
                cam, input_tensor, rgb_img, pred_idx,
                negative_class_idx=negative_idx,
                brightness_threshold=gradcam_brightness_threshold,
                erosion_pixels=gradcam_erosion_pixels,
            )

            heatmap_url = result.get("heatmap_url")
            heatmap_fs_path = result.get("heatmap_path")
            grayscale_cam = result["grayscale_cam"]

            if cfg.region_mapping_enabled and grayscale_cam is not None:
                from api.core.region_mapping import derive_affected_region
                region_info = derive_affected_region(grayscale_cam)
                affected_region = region_info["affected_region"]
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
            disease_type=disease_type,
            predicted_class=predicted_label,
            confidence=confidence,
            gradcam_path=heatmap_fs_path,
            extra_data={
                "all_class_probabilities": all_class_probabilities,
                "affected_region": affected_region,  # NEW, may be None
            },
            model_version=Path(cfg.checkpoint_path).name,
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
        disease_type=disease_type,
        disease=predicted_label,
        confidence=confidence,
        heatmap_url=heatmap_url,
        all_class_probabilities=all_class_probabilities,
        affected_region=affected_region,  # NEW
    )