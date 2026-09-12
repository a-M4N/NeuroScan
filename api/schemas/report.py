"""
Pydantic schemas for structured reports and clinical narrative generation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PredictionSummary(BaseModel):
    """Summarized prediction findings for a single scan."""
    prediction_id: int
    scan_id: int
    date: Optional[str] = None
    predicted_class: str
    confidence: float
    affected_region: Optional[str] = None
    gradcam_path: Optional[str] = None
    scan_path: Optional[str] = None
    all_class_probabilities: Optional[dict[str, float]] = None


class TrendInfo(BaseModel):
    """Longitudinal comparison between consecutive scans of the same condition."""
    trend_label: str = Field(
        ...,
        description="e.g. 'stable', 'progression', 'regression', 'new_finding', 'resolved', 'changed', 'insufficient_interval'",
    )
    summary: str
    previous_scan_date: Optional[str] = None
    previous_class: Optional[str] = None
    previous_confidence: Optional[float] = None
    current_scan_date: Optional[str] = None
    current_class: Optional[str] = None
    current_confidence: Optional[float] = None
    confidence_delta: Optional[float] = None
    scan_count: int


class DiseaseFindings(BaseModel):
    """Aggregated findings for a specific disease type."""
    disease_type: str
    latest: PredictionSummary
    history: list[PredictionSummary]
    trend: Optional[TrendInfo] = Field(
        default=None,
        description="Null/absent if only 1 scan exists for this disease",
    )


class StructuredFindings(BaseModel):
    """Aggregated patient findings across all evaluated diseases."""
    patient_id: int
    patient_name: str
    mrn: str
    date_of_birth: Optional[str] = None
    total_scans: int
    diseases: dict[str, DiseaseFindings]


class ReportResponse(BaseModel):
    """Response returned by POST /patients/{patient_id}/report."""
    id: Optional[int] = Field(None, description="Persisted Report row ID in database")
    patient_id: int
    generated_at: datetime
    structured_findings: StructuredFindings
    narrative_text: Optional[str] = Field(
        default=None,
        description="LLM-generated clinical narrative prose (null if LLM call fails or key unset)",
    )
    pdf_path: Optional[str] = None


class ReportListItem(BaseModel):
    """Response item for GET /patients/{patient_id}/reports."""
    id: int
    patient_id: int
    pdf_path: Optional[str] = None
    narrative_text: Optional[str] = None
    generated_at: datetime

    class Config:
        from_attributes = True
