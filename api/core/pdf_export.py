"""
PDF report generation module for NeuroScan.
Assembles patient demographic data, structured algorithmic findings,
side-by-side original MRI scans and Grad-CAM saliency heatmaps,
longitudinal trend trajectories, and the Gemini radiologic narrative
into a clinical-grade PDF document via Jinja2 and WeasyPrint.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

import jinja2
import markdown
from sqlalchemy.orm import Session

from api.core.report_builder import build_structured_findings
from api.db.models import Patient, Report

logger = logging.getLogger(__name__)

# Register GTK3 runtime DLL directory on Windows if available
if sys.platform == "win32":
    gtk_bin = r"C:\Program Files\GTK3-Runtime Win64\bin"
    if os.path.exists(gtk_bin):
        try:
            os.add_dll_directory(gtk_bin)
        except Exception as e:
            logger.debug(f"Could not register GTK3 DLL directory via os.add_dll_directory: {e}")

REPORTS_DIR = Path("data/reports")
TEMPLATE_DIR = Path("api/templates")


def _resolve_image_uri(file_path: Optional[str]) -> Optional[str]:
    """
    Converts a relative or absolute image path to a file:// URI that WeasyPrint can resolve.
    Returns None if file does not exist.
    """
    if not file_path:
        return None
    p = Path(file_path)
    if not p.is_absolute():
        if (Path.cwd() / p).exists():
            p = Path.cwd() / p
        elif (Path.cwd() / "data" / p).exists():
            p = Path.cwd() / "data" / p
        else:
            p = Path.cwd() / p
    if p.exists():
        return p.resolve().as_uri()
    logger.warning(f"Report image file not found on disk: {p}")
    return None


def generate_report_pdf(report_id: int, db: Session) -> Optional[str]:
    """
    Generates a clinical PDF report for the given report_id and saves it to disk.

    Args:
        report_id: Primary key of the Report record in PostgreSQL.
        db: SQLAlchemy database session.

    Returns:
        Relative file path string to the generated PDF (e.g. 'data/reports/report_1.pdf')
        or None if generation failed or dependencies are unavailable (fails non-fatally).
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        logger.error(f"Report with ID {report_id} not found.")
        return None

    patient = db.query(Patient).filter(Patient.id == report.patient_id).first()
    if not patient:
        logger.error(f"Patient {report.patient_id} for report {report_id} not found.")
        return None

    # Retrieve structured findings
    findings: Optional[dict[str, Any]] = build_structured_findings(report.patient_id, db)
    if not findings:
        logger.error(f"Could not build structured findings for patient {report.patient_id}.")
        return None

    # Enrich findings with file URIs for WeasyPrint image loading
    for disease_findings in findings.get("diseases", {}).values():
        latest = disease_findings.get("latest")
        if latest:
            latest["scan_uri"] = _resolve_image_uri(latest.get("scan_path"))
            latest["gradcam_uri"] = _resolve_image_uri(latest.get("gradcam_path"))

    # Convert Markdown narrative to HTML
    raw_narrative = report.narrative_text or ""
    if raw_narrative.strip():
        try:
            narrative_html = markdown.markdown(
                raw_narrative,
                extensions=["extra", "nl2br", "sane_lists"],
            )
        except Exception as e:
            logger.warning(f"Markdown conversion error for report {report_id}: {e}")
            narrative_html = f"<pre>{raw_narrative}</pre>"
    else:
        narrative_html = "<p><em>No diagnostic narrative was recorded for this report.</em></p>"

    # Format dates
    generated_at_formatted = (
        report.generated_at.strftime("%B %d, %Y %H:%M UTC")
        if report.generated_at
        else "N/A"
    )
    dob_formatted = (
        patient.date_of_birth.strftime("%Y-%m-%d")
        if patient.date_of_birth
        else "Unspecified"
    )

    # Render Jinja2 template
    try:
        jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )
        template = jinja_env.get_template("report_template.html")
        rendered_html = template.render(
            report_id=report.id,
            patient=patient,
            findings=findings,
            narrative_html=narrative_html,
            generated_at_formatted=generated_at_formatted,
            dob_formatted=dob_formatted,
        )
    except Exception as e:
        logger.error(f"Jinja2 template rendering failed for report {report_id}: {e}", exc_info=True)
        return None

    # Ensure reports directory exists
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_filename = f"report_{report.id}.pdf"
    pdf_filepath = REPORTS_DIR / pdf_filename

    # Compile HTML to PDF via WeasyPrint (fails non-fatally)
    try:
        import weasyprint  # lazy import to handle native lib issues cleanly

        html = weasyprint.HTML(
            string=rendered_html,
            base_url=str(Path.cwd()),
        )
        html.write_pdf(target=str(pdf_filepath))
        logger.info(f"Successfully generated PDF report at {pdf_filepath}")
    except (ImportError, OSError) as e:
        logger.error(f"WeasyPrint or system graphics library unavailable: {e}")
        return None
    except Exception as e:
        logger.error(f"PDF compilation failed for report {report_id}: {e}", exc_info=True)
        return None

    # Update database record with pdf_path
    try:
        normalized_path = str(pdf_filepath.as_posix())
        report.pdf_path = normalized_path
        db.commit()
        db.refresh(report)
        return normalized_path
    except Exception as e:
        logger.error(f"Failed to save pdf_path to database for report {report_id}: {e}")
        db.rollback()
        return str(pdf_filepath.as_posix())
