"""
Pydantic request/response schemas for the /predict endpoint.

Disease-agnostic as of Phase 5: `disease` and `all_class_probabilities`
are validated against the live DISEASE_CONFIGS registry at request time
(via the router), not against a hardcoded enum, since class labels now
differ per disease_type (brain_tumor vs alzheimers vs future diseases).
"""

from typing import Optional
from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """
    Metadata accompanying the uploaded file. The scan itself arrives as
    a multipart file upload (UploadFile), not in this body.
    """
    patient_id: str = Field(..., description="ID of the patient this scan belongs to")
    disease_type: str = Field(
        ..., description="Which classifier to run, e.g. 'brain_tumor', 'alzheimers'"
    )
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

    disease_type: str = Field(..., description="Which classifier produced this prediction")
    disease: str = Field(..., description="Predicted class label")
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Softmax probability of the predicted class",
    )
    heatmap_url: Optional[str] = Field(
        default=None,
        description=(
            "URL/path to the Grad-CAM overlay PNG. Null when the predicted "
            "class is that disease's negative/healthy class."
        ),
    )
    all_class_probabilities: dict[str, float] = Field(
        ...,
        description="Full softmax distribution over all classes for this disease_type",
    )
    affected_region: Optional[str] = Field(
        default=None,
        description=(
            "Coarse position label (e.g. 'upper-left region') derived from the "
            "Grad-CAM activation centroid. Position-based, not confirmed "
            "anatomical/radiological orientation — see api/core/region_mapping.py. "
            "Null when Grad-CAM wasn't generated or this disease doesn't opt in "
            "to region mapping."
        ),
    )


class PredictErrorResponse(BaseModel):
    """Returned with a 4xx/5xx status when preprocessing or inference fails."""
    detail: str