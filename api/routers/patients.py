"""
Basic patient CRUD + scan/prediction history lookup.
"""

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.db.database import get_db
from api.db.models import Patient, Report
from api.core.report_builder import build_structured_findings
from api.core.narrative import generate_narrative_report
from api.core.pdf_export import generate_report_pdf
from api.schemas.report import ReportResponse, ReportListItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["patients"])


# --- Schemas (kept local for now; move to api/schemas/patient.py if it grows) ---

class PatientCreate(BaseModel):
    name: str
    mrn: str
    date_of_birth: datetime | None = None


class PatientResponse(BaseModel):
    id: int
    name: str
    mrn: str
    date_of_birth: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionOut(BaseModel):
    id: int
    disease_type: str
    predicted_class: str
    confidence: float
    gradcam_path: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ScanOut(BaseModel):
    id: int
    file_path: str
    modality: str | None
    upload_date: datetime
    predictions: list[PredictionOut] = []

    class Config:
        from_attributes = True


# --- Routes ---

@router.post("", response_model=PatientResponse, status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    existing = db.query(Patient).filter(Patient.mrn == payload.mrn).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Patient with mrn '{payload.mrn}' already exists.")

    patient = Patient(name=payload.name, mrn=payload.mrn, date_of_birth=payload.date_of_birth)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientResponse])
def list_patients(db: Session = Depends(get_db)):
    return db.query(Patient).all()


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return patient


@router.get("/{patient_id}/scans", response_model=list[ScanOut])
def get_patient_scans(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return patient.scans


@router.get("/{patient_id}/predictions", response_model=list[PredictionOut])
def get_patient_predictions(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    predictions = [p for scan in patient.scans for p in scan.predictions]
    return predictions


@router.post("/{patient_id}/report", response_model=ReportResponse, status_code=201)
def generate_patient_report(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    findings = build_structured_findings(patient_id, db)
    narrative = generate_narrative_report(findings)

    generated_at = datetime.utcnow()
    report_id = None
    pdf_path = None

    try:
        report = Report(
            patient_id=patient.id,
            narrative_text=narrative,
            pdf_path=None,
            generated_at=generated_at,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        report_id = report.id
        generated_at = report.generated_at

        # Attempt non-fatal PDF generation immediately upon report creation
        try:
            pdf_path = generate_report_pdf(report.id, db)
        except Exception:
            logger.exception(f"Non-fatal error generating PDF for report {report.id}")
            pdf_path = None

    except Exception:
        db.rollback()
        logger.exception("Failed to persist Report row; continuing non-fatally")

    return ReportResponse(
        id=report_id,
        patient_id=patient.id,
        generated_at=generated_at,
        structured_findings=findings,
        narrative_text=narrative,
        pdf_path=pdf_path,
    )


@router.get("/{patient_id}/reports", response_model=list[ReportListItem])
def get_patient_reports(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return db.query(Report).filter(Report.patient_id == patient_id).order_by(Report.generated_at.desc()).all()


@router.get("/{patient_id}/reports/{report_id}", response_model=ReportListItem)
def get_patient_report_detail(patient_id: int, report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id, Report.patient_id == patient_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@router.post("/{patient_id}/reports/{report_id}/pdf")
def generate_or_regenerate_pdf(patient_id: int, report_id: int, db: Session = Depends(get_db)):
    """Explicitly generates or re-generates the PDF for a specific report."""
    report = db.query(Report).filter(Report.id == report_id, Report.patient_id == patient_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    pdf_path = generate_report_pdf(report.id, db)
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="Failed to generate PDF report.")

    return {"report_id": report.id, "pdf_path": pdf_path, "status": "generated"}


@router.get("/{patient_id}/reports/{report_id}/pdf")
def download_report_pdf(patient_id: int, report_id: int, db: Session = Depends(get_db)):
    """Downloads the compiled clinical PDF report."""
    report = db.query(Report).filter(Report.id == report_id, Report.patient_id == patient_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    pdf_path = report.pdf_path
    if not pdf_path or not os.path.exists(pdf_path):
        # Auto-generate if missing or not yet generated
        pdf_path = generate_report_pdf(report.id, db)

    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="PDF report could not be generated.")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"NeuroScan_Report_{report.id}.pdf",
    )