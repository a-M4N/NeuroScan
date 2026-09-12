"""
Comprehensive Phase 6 PDF Export Verification Script.
Tests:
1. Multi-case PDF generation:
   - Report 1 (Baseline single disease: Brain Tumor)
   - Report 4 (Multi-disease: Brain Tumor + Alzheimer's)
   - Report 12 (Longitudinal trend with time-gap awareness)
2. Integrity of generated PDF files (file existence, byte size, PDF header magic bytes)
3. API endpoints via FastAPI TestClient:
   - GET /patients/{id}/reports/{report_id}
   - GET /patients/{id}/reports/{report_id}/pdf (stream PDF)
   - POST /patients/{id}/reports/{report_id}/pdf (re-generate PDF)
   - 404 handling on invalid patient/report
4. Non-fatal fallback behavior:
   - Verify that if PDF generation encounters an error, the report/system does not crash
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from api.main import app
from api.db.database import SessionLocal
from api.db.models import Report, Patient
from api.core.pdf_export import generate_report_pdf

def test_multicase_pdf_export():
    print("=================================================================")
    print("STEP 6 VERIFICATION: NEUROSCAN CLINICAL PDF REPORT EXPORT")
    print("=================================================================")
    
    db = SessionLocal()
    client = TestClient(app)
    
    test_cases = [
        {"report_id": 1, "patient_id": 1, "label": "Baseline Scan (Brain Tumor)"},
        {"report_id": 4, "patient_id": 5, "label": "Multi-Disease Scan (Brain Tumor + Alzheimer's)"},
        {"report_id": 12, "patient_id": 6, "label": "Longitudinal Follow-up (Interval-aware Trend)"}
    ]
    
    print("\n--- 1. Multi-case PDF Generation & Disk Inspection ---")
    for case in test_cases:
        rid = case["report_id"]
        pid = case["patient_id"]
        label = case["label"]
        
        pdf_path = generate_report_pdf(rid, db)
        assert pdf_path is not None, f"PDF path returned None for report {rid}"
        p = Path(pdf_path)
        assert p.exists(), f"PDF file does not exist on disk at {pdf_path}"
        
        file_size = p.stat().st_size
        assert file_size > 10000, f"PDF file size suspiciously small ({file_size} bytes)"
        
        # Verify PDF magic bytes
        with open(p, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-", f"File {pdf_path} does not begin with %PDF- header"
            
        # Verify DB persistence
        report = db.query(Report).filter(Report.id == rid).first()
        assert report.pdf_path == pdf_path, f"DB pdf_path ({report.pdf_path}) does not match expected ({pdf_path})"
        
        print(f"  [OK] Report #{rid} (Patient #{pid}, {label})")
        print(f"       -> Path: {pdf_path} | Size: {file_size:,} bytes | Magic: %PDF- verified | DB updated: True")
        
    print("\n--- 2. FastAPI Endpoint Testing ---")
    
    # Test GET metadata
    print("Testing GET /patients/1/reports/1 (Metadata)...")
    res = client.get("/patients/1/reports/1")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert data["id"] == 1
    assert data["pdf_path"] == "data/reports/report_1.pdf"
    print(f"  [OK] Metadata response: id={data['id']}, patient_id={data['patient_id']}, pdf_path={data['pdf_path']}")
    
    # Test GET /pdf streaming
    print("\nTesting GET /patients/1/reports/1/pdf (Streaming PDF)...")
    res = client.get("/patients/1/reports/1/pdf")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert res.headers.get("content-type") == "application/pdf", f"Unexpected content-type {res.headers.get('content-type')}"
    assert 'attachment; filename="NeuroScan_Report_1.pdf"' in res.headers.get("content-disposition", "")
    assert len(res.content) > 10000
    assert res.content[:5] == b"%PDF-"
    print(f"  [OK] Streamed PDF: {len(res.content):,} bytes, Content-Disposition: {res.headers.get('content-disposition')}")
    
    # Test GET /pdf for Multi-disease Report 4
    print("\nTesting GET /patients/5/reports/4/pdf (Multi-disease Streaming)...")
    res = client.get("/patients/5/reports/4/pdf")
    assert res.status_code == 200
    assert res.headers.get("content-type") == "application/pdf"
    assert len(res.content) > 10000
    print(f"  [OK] Streamed Multi-disease PDF: {len(res.content):,} bytes")
    
    # Test GET /pdf for Longitudinal Report 12
    print("\nTesting GET /patients/6/reports/12/pdf (Longitudinal Streaming)...")
    res = client.get("/patients/6/reports/12/pdf")
    assert res.status_code == 200
    assert res.headers.get("content-type") == "application/pdf"
    assert len(res.content) > 10000
    print(f"  [OK] Streamed Longitudinal PDF: {len(res.content):,} bytes")
    
    # Test POST /pdf re-generation
    print("\nTesting POST /patients/1/reports/1/pdf (Explicit Re-generation)...")
    res = client.post("/patients/1/reports/1/pdf")
    assert res.status_code == 200
    data = res.json()
    assert data.get("pdf_path") == "data/reports/report_1.pdf"
    print(f"  [OK] Re-generated report: {data}")
    
    # Test 404 edge cases
    print("\nTesting 404 error cases...")
    res = client.get("/patients/9999/reports/1/pdf")
    assert res.status_code == 404, f"Expected 404, got {res.status_code}"
    print(f"  [OK] Patient mismatch -> 404 Not Found")
    
    res = client.get("/patients/1/reports/99999/pdf")
    assert res.status_code == 404, f"Expected 404, got {res.status_code}"
    print(f"  [OK] Non-existent report -> 404 Not Found")
    
    print("\n--- 3. Non-Fatal Fallback Verification ---")
    # Verify that if generate_report_pdf is called with an invalid report, it returns None gracefully without throwing
    res_invalid = generate_report_pdf(99999, db)
    assert res_invalid is None
    print("  [OK] Invalid report ID gracefully returned None without raising unhandled exception.")

    db.close()
    print("\n=================================================================")
    print("ALL PHASE 6 PDF EXPORT VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=================================================================")

if __name__ == "__main__":
    test_multicase_pdf_export()
