"""
Pydantic request/response schemas for the /predict endpoint.

This is the data contract between the API and everything downstream —
the frontend dashboard, and eventually the PostgreSQL prediction table
(Phase 4) and the Claude-generated narrative report (Phase 6). Keep this
stable once other layers start depending on it.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TumorClass(str, Enum):
    """Mirrors CLASS_LABELS in models/src/model.py — keep in sync."""
    glioma = "glioma"
    meningioma = "meningioma"
    no_tumor = "no_tumor"
    pituitary = "pituitary"


class PredictRequest(BaseModel):
    """
    Metadata accompanying the uploaded file. The scan itself arrives as
    a multipart file upload (UploadFile), not in this body — FastAPI
    will parse this alongside the file using Form(...) fields, or this
    can represent the JSON part of a mixed request.
    """
    patient_id: str = Field(..., description="ID of the patient this scan belongs to")
    slice_index: Optional[int] = Field(
        default=None,
        description=(
            "Which axial slice to analyze, for NIfTI/DICOM volumes. "
            "Defaults to the middle slice if not provided. Ignored for "
            "2D image uploads (jpg/png)."
        ),
    )


class PredictionResponse(BaseModel):
    """Response returned by POST /predict."""

    disease: TumorClass = Field(..., description="Predicted class")
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Softmax probability of the predicted class",
    )
    heatmap_url: Optional[str] = Field(
        default=None,
        description=(
            "URL/path to the Grad-CAM overlay PNG. Null when disease is "
            "no_tumor, since no heatmap is generated for healthy scans."
        ),
    )
    all_class_probabilities: dict[TumorClass, float] = Field(
        ...,
        description="Full softmax distribution over all 4 classes, for transparency/debugging",
    )

    class Config:
        use_enum_values = True


class PredictErrorResponse(BaseModel):
    """Returned with a 4xx/5xx status when preprocessing or inference fails."""
    detail: str