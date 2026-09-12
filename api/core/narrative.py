"""
LLM-powered clinical narrative generation using Google Gemini Flash.

Translates pre-computed structured findings from api/core/report_builder.py into
clinical-style narrative prose.

STRICT CONSTRAINTS (per project architecture and README principles):
- The LLM ONLY phrases pre-computed structured findings.
- It NEVER makes diagnostic judgments, infers unmentioned conditions, or adds
  clinical claims beyond the structured data.
- The 'affected_region' is explicitly image-position-based, NOT an anatomically
  confirmed localization. The prompt explicitly forces hedging (e.g. "activity
  was concentrated in the upper-central portion of the imaged slice").
- Longitudinal trends are discussed ONLY if pre-computed in Step 2.
- Failures fail non-fatally: returns None if the API key is missing or the call
  errors, allowing the caller to still return structured findings.
"""

import json
import logging
import os
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")


def build_narrative_prompt(findings: dict[str, Any]) -> str:
    """
    Constructs a constrained, structured prompt ensuring the LLM acts solely as a
    medical scribe/phraser of structured findings.
    """
    patient_summary = (
        f"Patient Name: {findings.get('patient_name', 'Unknown')}\n"
        f"MRN: {findings.get('mrn', 'Unknown')}\n"
        f"Date of Birth: {findings.get('date_of_birth', 'Not recorded')}\n"
        f"Total Scans on Record: {findings.get('total_scans', 1)}"
    )

    diseases_data = findings.get("diseases", {})
    diseases_str = json.dumps(diseases_data, indent=2)

    prompt = f"""You are an objective clinical medical scribe translating verified AI imaging analysis results into a structured diagnostic narrative report.

CRITICAL CLINICAL & ETHICAL INVARIANTS:
1. STRICT REPHRASING ONLY: Do NOT diagnose, invent, extrapolate, or infer any disease, condition, or severity stage not explicitly present in the data below.
2. POSITION-BASED LOCALIZATION HEDGE: The 'affected_region' field is purely a 2D image coordinate/position centroid (e.g. 'upper-left region', 'central region') derived from Grad-CAM heatmaps. It is NOT an anatomically confirmed or radiologically verified anatomical structure. You MUST describe it strictly as an image-slice position hedge (for example: "model attention was concentrated in the upper-central aspect of the imaged slice") and NEVER name specific anatomical lobes, gyri, or hemispheres.
3. LONGITUDINAL TRENDS:
   - If 'trend' is present for a condition:
     - If 'trend_label' is 'insufficient_interval': The scans occurred in rapid succession (within an interval below clinical follow-up threshold). You MUST explicitly state that the brief timeframe between scans precludes a meaningful longitudinal or progression assessment, note that it likely reflects a duplicate or rapid repeat/QA acquisition, and NEVER describe differences as disease progression, regression, or genuine clinical change.
     - Otherwise (valid clinical interval): Synthesize the comparison between prior and current scans (stating dates, change in classification, or confidence delta).
   - If 'trend' is null or absent: Explicitly treat the scan as an isolated baseline evaluation. NEVER speculate on progression or stability without pre-computed trend data.
4. TONE & STYLE: Write in professional, objective clinical report language. Be concise, clear, and unambiguous.

PATIENT INFORMATION:
{patient_summary}

PRE-COMPUTED STRUCTURED FINDINGS:
{diseases_str}

Please generate the report with the following clear section headers:
- CLINICAL STUDY SUMMARY (Patient identification and overview of conditions assessed)
- OBJECTIVE FINDINGS (Detailed narrative of findings for each condition evaluated, including classification, confidence percentage, and spatial position hedge if applicable)
- LONGITUDINAL COMPARISON (Include ONLY for conditions that have pre-computed trend data; if trend_label is 'insufficient_interval', clearly state that the rapid acquisition interval precludes longitudinal evaluation; if all conditions are baseline single scans, state that prior imaging is unavailable for comparison)
- IMPRESSION (Concise summary synthesizing the above findings strictly within the boundary of the provided data)
"""
    return prompt


def generate_narrative_report(findings: dict[str, Any]) -> Optional[str]:
    """
    Calls Google Gemini Flash to generate clinical narrative prose from structured findings.

    Returns:
        Generated narrative prose as a string, or None if the call fails or API key is not set.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured; skipping narrative generation.")
        return None

    if not findings.get("diseases"):
        logger.info("No disease predictions found for patient; skipping narrative generation.")
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        prompt = build_narrative_prompt(findings)

        # Attempt with configured model, falling back if needed
        model_name = DEFAULT_MODEL
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            if model_name != "gemini-flash-latest":
                logger.warning(f"Failed with model '{model_name}': {e}. Attempting fallback to 'gemini-flash-latest'.")
                fallback_model = genai.GenerativeModel("gemini-flash-latest")
                fallback_response = fallback_model.generate_content(prompt)
                if fallback_response and fallback_response.text:
                    return fallback_response.text.strip()
            else:
                logger.error(f"Failed to generate narrative with '{model_name}': {e}")

    except Exception:
        logger.exception("Failed to generate narrative report via Gemini (failing non-fatally)")
        return None

    return None
