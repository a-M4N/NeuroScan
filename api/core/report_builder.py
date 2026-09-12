"""
Core logic for aggregating a patient's historical scans and predictions
into structured clinical findings with longitudinal trend analysis.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session

from api.db.models import Patient, Scan, Prediction
from models.src.disease_configs import DISEASE_CONFIGS, DiseaseConfig


import os

MIN_TREND_GAP_HOURS = float(os.getenv("MIN_TREND_GAP_HOURS", "1.0"))


def build_structured_findings(patient_id: int, db: Session) -> Optional[dict[str, Any]]:
    """
    Queries all Scan and Prediction records for a patient and aggregates them
    into a structured findings dictionary partitioned by disease_type.

    For each disease_type with predictions:
      - latest: most recent prediction record (class, confidence, region, gradcam, date)
      - history: full chronologically ordered prediction history
      - trend: longitudinal trend comparison between prior and latest scan if 2+ scans exist,
               or None if only 1 scan exists.
               If 2+ scans were taken too close together (< MIN_TREND_GAP_HOURS), sets
               trend_label to 'insufficient_interval' to avoid treating QA/duplicate
               uploads as genuine longitudinal follow-ups.

    Returns:
        Structured findings dict or None if patient does not exist.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        return None

    # Query all predictions for this patient ordered chronologically
    predictions = (
        db.query(Prediction)
        .join(Scan, Prediction.scan_id == Scan.id)
        .filter(Scan.patient_id == patient_id)
        .order_by(Prediction.created_at.asc())
        .all()
    )

    # Group predictions by disease_type
    grouped: dict[str, list[dict[str, Any]]] = {}
    for p in predictions:
        extra = p.extra_data or {}
        pred_record = {
            "prediction_id": p.id,
            "scan_id": p.scan_id,
            "date": p.created_at.isoformat() if p.created_at else None,
            "created_at_dt": p.created_at,
            "predicted_class": p.predicted_class,
            "confidence": round(float(p.confidence), 4),
            "affected_region": extra.get("affected_region"),
            "gradcam_path": p.gradcam_path,
            "scan_path": p.scan.file_path if p.scan else None,
            "all_class_probabilities": extra.get("all_class_probabilities"),
        }
        grouped.setdefault(p.disease_type, []).append(pred_record)

    # Build per-disease structured findings and trends
    diseases_findings: dict[str, Any] = {}
    for disease_type, history in grouped.items():
        latest = {k: v for k, v in history[-1].items() if k != "created_at_dt"}
        clean_history = [{k: v for k, v in h.items() if k != "created_at_dt"} for h in history]
        trend = None

        # Compute trend only if 2 or more scans exist for this disease_type
        if len(history) >= 2:
            prev = history[-2]
            curr = history[-1]
            cfg: Optional[DiseaseConfig] = DISEASE_CONFIGS.get(disease_type)

            prev_class = prev["predicted_class"]
            curr_class = curr["predicted_class"]
            conf_delta = round(curr["confidence"] - prev["confidence"], 4)

            # Check time interval between the two predictions
            prev_dt = prev.get("created_at_dt")
            curr_dt = curr.get("created_at_dt")
            is_insufficient_interval = False
            interval_str = ""

            if prev_dt and curr_dt:
                delta_sec = abs((curr_dt - prev_dt).total_seconds())
                gap_hours = delta_sec / 3600.0
                if gap_hours < MIN_TREND_GAP_HOURS:
                    is_insufficient_interval = True
                    if delta_sec < 60:
                        interval_str = f"{int(delta_sec)}s"
                    elif delta_sec < 3600:
                        interval_str = f"{int(delta_sec // 60)}m {int(delta_sec % 60)}s"
                    else:
                        interval_str = f"{round(gap_hours, 2)}h"

            if is_insufficient_interval:
                trend_label = "insufficient_interval"
                summary = (
                    f"Scans occurred within {interval_str} of each other (minimum threshold: {MIN_TREND_GAP_HOURS}h). "
                    "This interval is too short to evaluate a meaningful clinical trajectory; "
                    "likely a duplicate upload, re-run, or QA scan."
                )
            elif cfg and cfg.severity_order:
                # Ordinal severity comparison
                if prev_class in cfg.severity_order and curr_class in cfg.severity_order:
                    rank_prev = cfg.severity_order.index(prev_class)
                    rank_curr = cfg.severity_order.index(curr_class)

                    if rank_curr > rank_prev:
                        trend_label = "progression"
                        summary = f"Progression: status changed from {prev_class} to {curr_class}."
                    elif rank_curr < rank_prev:
                        trend_label = "regression"
                        summary = f"Improvement: status changed from {prev_class} to {curr_class}."
                    else:
                        trend_label = "stable"
                        summary = f"Stable classification ({curr_class}) across consecutive scans."
                else:
                    trend_label = "stable" if prev_class == curr_class else "changed"
                    summary = f"Classification changed from {prev_class} to {curr_class}."
            else:
                # Categorical comparison (when severity_order is None, e.g. brain_tumor)
                if curr_class == prev_class:
                    trend_label = "stable"
                    summary = f"Consistent classification of {curr_class} across scans."
                else:
                    if cfg and cfg.negative_class and prev_class == cfg.negative_class:
                        trend_label = "new_finding"
                        summary = f"New finding: previously {prev_class}, now classified as {curr_class}."
                    elif cfg and cfg.negative_class and curr_class == cfg.negative_class:
                        trend_label = "resolved"
                        summary = f"Status resolved to {curr_class}, previously {prev_class}."
                    else:
                        trend_label = "changed"
                        summary = f"Classification shifted from {prev_class} to {curr_class}."

            trend = {
                "trend_label": trend_label,
                "summary": summary,
                "previous_scan_date": prev["date"],
                "previous_class": prev_class,
                "previous_confidence": prev["confidence"],
                "current_scan_date": curr["date"],
                "current_class": curr_class,
                "current_confidence": curr["confidence"],
                "confidence_delta": conf_delta,
                "scan_count": len(history),
            }

        diseases_findings[disease_type] = {
            "disease_type": disease_type,
            "latest": latest,
            "history": clean_history,
            "trend": trend,
        }

    return {
        "patient_id": patient.id,
        "patient_name": patient.name,
        "mrn": patient.mrn,
        "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        "total_scans": len(patient.scans),
        "diseases": diseases_findings,
    }
