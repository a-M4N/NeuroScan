"""
Basic patient CRUD + scan/prediction history lookup.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.db.database import get_db
from api.db.models import Patient

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