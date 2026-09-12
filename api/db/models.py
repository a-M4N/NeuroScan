from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy import JSON 
from api.db.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    mrn = Column(String, unique=True, index=True, nullable=False)  # medical record number
    date_of_birth = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    scans = relationship("Scan", back_populates="patient", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="patient", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    file_path = Column(String, nullable=False)
    modality = Column(String, nullable=True)  # e.g. "MRI", "NIfTI", "DICOM"
    upload_date = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="scans")
    predictions = relationship("Prediction", back_populates="scan", cascade="all, delete-orphan")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False)
    disease_type = Column(String, nullable=False, index=True)  # added index
    predicted_class = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    gradcam_path = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)      # NEW — per-disease structured extras
    model_version = Column(String, nullable=True) # NEW — checkpoint filename/tag used
    created_at = Column(DateTime, default=datetime.utcnow)

    scan = relationship("Scan", back_populates="predictions")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    pdf_path = Column(String, nullable=True)
    narrative_text = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="reports")