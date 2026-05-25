"""PDF-Rendering via PyMuPDF (fitz) fuer die KI-Extraktion.

PyMuPDF ist pure-Python (via pip-wheel mit native binding),
braucht kein Poppler/Ghostscript. Deutlich einfacheres Deployment
als Alternativen (pdf2image, Wand, etc.).

Jede Seite wird als PNG-Bytes zurueckgegeben und direkt an die Vision-API uebergeben.
"""

from __future__ import annotations


def render_pdf_to_png_pages(
    pdf_bytes: bytes,
    max_pages: int = 10,
    dpi: int = 150,
) -> list[bytes]:
    """Rendert PDF-Seiten zu PNG-Bytes via PyMuPDF (fitz). Synchron, CPU-bound.

    max_pages=10 schuetzt vor Riesen-PDFs, die das Vision-Modell ueberlasten wuerden.
    dpi=150 ist ein guter Kompromiss zwischen Qualitaet und Datenmenge fuer OCR.

    Gibt eine Liste von PNG-Bytes zurueck (eine Liste-Element pro Seite).
    """
    import fitz  # PyMuPDF - import hier damit Tests ohne pymupdf laufen koennen

    pages: list[bytes] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        num_pages = min(doc.page_count, max_pages)
        mat = fitz.Matrix(dpi / 72, dpi / 72)  # 72 DPI = 1:1, skaliert auf dpi
        for page_idx in range(num_pages):
            page = doc.load_page(page_idx)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pages.append(pix.tobytes("png"))
    finally:
        doc.close()

    return pages
