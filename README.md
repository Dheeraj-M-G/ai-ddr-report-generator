# Detailed Diagnostic Report (DDR) Generator

End-to-end Python application that reads two PDFs—an **Inspection Report** and a **Thermal Report**—extracts text and images with **PyMuPDF (fitz)**, analyzes them with **OpenAI GPT** (or optional **Google Gemini**), and produces a **Detailed Diagnostic Report** as **DOCX** and **PDF**.

## Project overview

The system is designed for production-style use: modular modules, structured JSON from the LLM, strict “no hallucination” rules in prompts, caching of LLM responses, logging, and a simple **Streamlit** UI for uploads and downloads.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Streamlit  │────▶│ pdf_processing   │────▶│ extracted_images│
│   app.py    │     │ (PyMuPDF)        │     │ + text blobs    │
└─────────────┘     └──────────────────┘     └────────┬────────┘
       │                                              │
       │              ┌──────────────────┐            │
       └─────────────▶│ llm_processing   │◀───────────┘
                      │ (OpenAI/Gemini)  │
                      └────────┬─────────┘
                               │ structured JSON
                      ┌────────▼─────────┐
                      │ report_generator │
                      │ (DOCX + PDF)     │
                      └────────┬─────────┘
                               ▼
                         outputs/ (DOCX, PDF, JSON)
```

| File | Role |
|------|------|
| `app.py` | Streamlit UI: uploads, button, preview, downloads |
| `pdf_processing.py` | Extract text and images from both PDFs |
| `llm_processing.py` | Prompts + API calls; returns structured DDR JSON |
| `report_generator.py` | Builds DOCX (`python-docx`) and PDF (`reportlab`) |
| `utils.py` | Paths, logging, JSON helpers, in-memory LLM cache |
| `extracted_images/` | Saved raster images from PDFs |
| `outputs/` | Generated DOCX, PDF, and JSON snapshot |

## Setup

### 1. Python environment

```bash
cd "path/to/New folder"
python -m venv .venv
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS/Linux:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. API keys

**OpenAI (default):**

```powershell
$env:OPENAI_API_KEY = "sk-..."
# optional model override:
$env:OPENAI_MODEL = "gpt-4o-mini"
```

**Gemini (optional):**

```powershell
$env:DDR_LLM_PROVIDER = "gemini"
$env:GEMINI_API_KEY = "..."
# optional:
$env:GEMINI_MODEL = "gemini-1.5-flash"
```

### 3. Streamlit Cloud

Add **Secrets** (TOML):

```toml
OPENAI_API_KEY = "sk-..."
```

Optional:

```toml
OPENAI_MODEL = "gpt-4o-mini"
```

For Gemini:

```toml
DDR_LLM_PROVIDER = "gemini"
GEMINI_API_KEY = "..."
```

## How to run

```bash
streamlit run app.py
```

Open the URL shown in the terminal (typically `http://localhost:8501`).

## Example usage

1. Start the app.
2. Upload **Inspection Report** PDF and **Thermal Report** PDF.
3. Click **Generate DDR Report**.
4. Review **Extracted summary**, **JSON preview**, and **Final report preview**.
5. Download **DOCX**, **PDF**, or **JSON** as needed.

## Output behavior

- **Structured JSON** is produced first (with fields such as `area`, `issue`, `description`, `thermal_observation`, `combined_insight`, `severity`, `recommendation`, `image_reference`).
- Prompts require **“Not Available”** for missing data and explicit **conflicts** when sources disagree.
- **Images** are stored under `extracted_images/`; the report references them by filename when the model maps an observation to a file. If none apply, the report states **Image Not Available**.
- A **JSON snapshot** is saved under `outputs/` for auditing.

## Limitations

- Quality depends on PDF text extraction (scanned PDFs without OCR may yield little text).
- The model does not “see” pixels unless you extend the pipeline with vision APIs; filenames are hints only, as stated in prompts.
- Very large PDFs are truncated for the LLM (see `llm_processing.py` character limits).
- **PDF** export uses ReportLab (clean layout); **DOCX** may look richer for images and headings.
- **Caching** is in-process only (resets when the app restarts).

## Future improvements

- Optional **OCR** (e.g. Tesseract, cloud OCR) for scanned documents.
- **Vision** model pass to align images with observations when needed.
- Persistent cache (Redis/disk) and user-configurable models/temperature.
- Stronger validation of LLM JSON against a **JSON Schema** (e.g. Pydantic).
- Batch processing and REST API wrapper.

## License

Use and modify for your project as needed.
