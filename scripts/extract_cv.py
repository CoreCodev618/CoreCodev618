#!/usr/bin/env python3
"""
extract_cv.py - Extrae datos del CV en PDF y los guarda en data/profile.json
"""
import json
import sys
from pathlib import Path

try:
    import PyPDF2
except ImportError:
    print("ERROR: Instala PyPDF2 con: pip install PyPDF2")
    sys.exit(1)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrae todo el texto de un archivo PDF."""
    text = ""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text


def main():
    pdf_path = Path("CV.pdf")
    if not pdf_path.exists():
        print(f"ERROR: No se encontró {pdf_path}")
        sys.exit(1)

    text = extract_text_from_pdf(str(pdf_path))
    print(f"Texto extraído ({len(text)} caracteres):")
    print("=" * 50)
    print(text[:2000])
    print("=" * 50)

    # Guardar texto crudo para referencia
    output_path = Path("data/cv_raw.txt")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    print(f"\nTexto guardado en {output_path}")


if __name__ == "__main__":
    main()
