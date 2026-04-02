"""
Streamlit UI: upload Inspection + Thermal PDFs, generate Detailed Diagnostic Report (DDR).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from llm_processing import generate_ddr_json
from pdf_processing import extract_two_reports
from report_generator import build_ddr_docx, save_json_snapshot
from utils import ensure_directories, get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

st.set_page_config(page_title="DDR Generator", layout="wide")
ensure_directories()

st.title("Detailed Diagnostic Report (DDR) Generator")
st.caption(
    "Upload an Inspection Report PDF and a Thermal Report PDF. "
    "The app extracts text and images, runs AI analysis, and produces a DOCX and PDF report."
)

with st.sidebar:
    st.subheader("API configuration")
    st.markdown(
        "Set `OPENAI_API_KEY` in environment (or Streamlit Cloud **Secrets**). "
        "Optional: `DDR_LLM_PROVIDER=gemini` with `GEMINI_API_KEY`."
    )
    st.code("OPENAI_API_KEY=sk-...\n# optional:\n# DDR_LLM_PROVIDER=gemini\n# GEMINI_API_KEY=...", language="text")

inspection_file = st.file_uploader("Inspection Report (PDF)", type=["pdf"])
thermal_file = st.file_uploader("Thermal Report (PDF)", type=["pdf"])

if st.button("Generate DDR Report", type="primary"):
    if not inspection_file or not thermal_file:
        st.error("Please upload both PDF files.")
    else:
        with st.spinner("Extracting PDFs and running analysis…"):
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    insp_path = tmp_path / "inspection.pdf"
                    therm_path = tmp_path / "thermal.pdf"
                    insp_path.write_bytes(inspection_file.getvalue())
                    therm_path.write_bytes(thermal_file.getvalue())

                    inspection_pdf, thermal_pdf = extract_two_reports(insp_path, therm_path)
                    all_images = inspection_pdf.image_paths + thermal_pdf.image_paths

                    ddr_data = generate_ddr_json(
                        inspection_pdf.full_text,
                        thermal_pdf.full_text,
                        all_images,
                        use_cache=True,
                    )
                    json_path = save_json_snapshot(ddr_data)
                    docx_path, pdf_path = build_ddr_docx(ddr_data)

                    st.session_state["ddr_data"] = ddr_data
                    st.session_state["json_path"] = str(json_path)
                    st.session_state["docx_path"] = str(docx_path)
                    st.session_state["pdf_path"] = str(pdf_path)
                    st.session_state["summary"] = {
                        "inspection_pages": inspection_pdf.page_count,
                        "thermal_pages": thermal_pdf.page_count,
                        "inspection_chars": len(inspection_pdf.full_text),
                        "thermal_chars": len(thermal_pdf.full_text),
                        "images_extracted": len(all_images),
                    }

                st.success("Report generated successfully.")
            except FileNotFoundError as e:
                st.error(f"File error: {e}")
                logger.exception("File not found")
            except RuntimeError as e:
                st.error(f"Configuration error: {e}")
                logger.exception("Runtime error")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
                logger.exception("Pipeline failed")

if "summary" in st.session_state:
    st.subheader("Extracted summary")
    st.json(st.session_state["summary"])

if "ddr_data" in st.session_state:
    st.subheader("Structured JSON (preview)")
    preview = json.dumps(st.session_state["ddr_data"], indent=2, ensure_ascii=False)
    st.text_area("DDR JSON", preview[:12000] + ("…" if len(preview) > 12000 else ""), height=320)

    st.subheader("Final report preview (text)")
    d = st.session_state["ddr_data"]
    st.markdown(f"**1. Property Issue Summary**  \n{d.get('property_issue_summary', 'Not Available')}")
    obs = d.get("observations") or []
    st.markdown("**2. Area-wise Observations**")
    if not obs:
        st.write("No observations.")
    for o in obs[:15]:
        st.markdown(
            f"- **{o.get('area', 'Not Available')}**: {o.get('issue', 'Not Available')} — "
            f"{o.get('description', 'Not Available')}"
        )
    if len(obs) > 15:
        st.caption(f"… and {len(obs) - 15} more in the downloaded files.")

if "docx_path" in st.session_state:
    c1, c2, c3 = st.columns(3)
    with c1:
        with open(st.session_state["docx_path"], "rb") as f:
            st.download_button(
                "Download DOCX",
                data=f.read(),
                file_name=Path(st.session_state["docx_path"]).name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
    with c2:
        with open(st.session_state["pdf_path"], "rb") as f:
            st.download_button(
                "Download PDF",
                data=f.read(),
                file_name=Path(st.session_state["pdf_path"]).name,
                mime="application/pdf",
            )
    with c3:
        if "json_path" in st.session_state:
            with open(st.session_state["json_path"], "rb") as f:
                st.download_button(
                    "Download JSON",
                    data=f.read(),
                    file_name=Path(st.session_state["json_path"]).name,
                    mime="application/json",
                )
