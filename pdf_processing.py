"""
PDF extraction using PyMuPDF (fitz): full text and embedded images per document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

from utils import EXTRACTED_IMAGES_DIR, ensure_directories, get_logger

logger = get_logger(__name__)


@dataclass
class ExtractedPDF:
    """Result of processing one PDF file."""

    source_path: Path
    full_text: str
    # Paths to saved image files (under extracted_images), relative names or absolute
    image_paths: List[Path] = field(default_factory=list)
    page_count: int = 0


def _unique_image_path(base_dir: Path, stem: str, ext: str, index: int) -> Path:
    """Avoid overwriting when multiple images share a name."""
    candidate = base_dir / f"{stem}_{index}{ext}"
    n = index
    while candidate.exists():
        n += 1
        candidate = base_dir / f"{stem}_{n}{ext}"
    return candidate


def extract_pdf(pdf_path: Path, prefix: str) -> ExtractedPDF:
    """
    Extract all text and images from a PDF.

    :param pdf_path: Path to the PDF file.
    :param prefix: Short label for image filenames (e.g. 'inspection' or 'thermal').
    :return: ExtractedPDF with concatenated text and list of saved image paths.
    """
    ensure_directories()
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    text_parts: List[str] = []
    image_paths: List[Path] = []
    img_counter = 0

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            text_parts.append(page.get_text("text") or "")
            # Images on this page
            image_list = page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                try:
                    base = doc.extract_image(xref)
                except Exception as e:
                    logger.warning("Skipping image xref=%s on page %s: %s", xref, page_index, e)
                    continue
                img_bytes = base.get("image")
                ext = base.get("ext", "png")
                if not img_bytes:
                    continue
                img_counter += 1
                stem = f"{prefix}_p{page_index + 1}"
                out_path = _unique_image_path(EXTRACTED_IMAGES_DIR, stem, f".{ext}", img_counter)
                try:
                    out_path.write_bytes(img_bytes)
                    image_paths.append(out_path)
                except OSError as e:
                    logger.warning("Could not write image %s: %s", out_path, e)

        full_text = "\n\n".join(t for t in text_parts if t.strip())
        if not full_text.strip():
            full_text = "Not Available"
            logger.info("No text extracted from %s; placeholder used.", pdf_path.name)

        return ExtractedPDF(
            source_path=pdf_path,
            full_text=full_text,
            image_paths=image_paths,
            page_count=len(doc),
        )
    finally:
        doc.close()


def extract_two_reports(
    inspection_pdf: Path,
    thermal_pdf: Path,
) -> tuple[ExtractedPDF, ExtractedPDF]:
    """
    Extract inspection and thermal PDFs with distinct image filename prefixes.
    """
    inspection = extract_pdf(inspection_pdf, prefix="inspection")
    thermal = extract_pdf(thermal_pdf, prefix="thermal")
    return inspection, thermal
