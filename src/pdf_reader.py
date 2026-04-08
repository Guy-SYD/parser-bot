import pdfplumber
from pathlib import Path


def extract_pages(pdf_path: str) -> list[dict]:
    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = []

    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            words = page.extract_words() or []
            lines = [line.strip() for line in text.splitlines() if line.strip()]

            pages.append({
                "page_number": i,
                "text": text,
                "lines": lines,
                "word_count": len(words),
                "char_count": len(text),
            })

    return pages
