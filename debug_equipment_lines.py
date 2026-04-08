"""
debug_equipment_lines.py

Loops through every PDF in samples/, extracts all section content,
and writes a labelled dump to output/equipment_lines.txt.

Sections currently SKIPPED by the parser (mechanical/engineering) are
marked with [SKIPPED] so you can see what lines need keyword routing.
Equipment sections actively collected are marked with their subtab name.
Lines before any known heading are shown under [NO SECTION DETECTED].

Run:
    python debug_equipment_lines.py
"""

import sys
from pathlib import Path

# Add src/ to path so we can import the existing modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pdf_reader import extract_pages
from extract_sections import HEADING_TO_SUBTAB, _normalize, _is_skip_line

import re


def classify_line(line: str):
    """Same logic as extract_sections._classify_line but returns raw HEADING_TO_SUBTAB value."""
    norm = _normalize(line)
    if len(norm) > 90:
        return "CONTENT"
    if norm in HEADING_TO_SUBTAB:
        val = HEADING_TO_SUBTAB[norm]
        return val  # None = skipped heading, str = active subtab
    for heading, subtab in HEADING_TO_SUBTAB.items():
        if heading and norm.endswith(heading):
            return subtab
    return "CONTENT"


def dump_pdf(pdf_path: Path) -> list[str]:
    """Extract and label every content line from a PDF."""
    pages = extract_pages(str(pdf_path))
    output = []
    current_label = "NO SECTION DETECTED"
    current_is_skip = False

    for page in pages:
        for raw_line in page.get("lines", []):
            line = raw_line.strip()
            if not line:
                continue

            result = classify_line(line)

            if result != "CONTENT":
                # It's a heading — update current section
                if result is None:
                    # Skipped section (mechanical etc.)
                    current_label = _normalize(line).upper()
                    current_is_skip = True
                else:
                    # Active equipment subtab
                    current_label = result
                    current_is_skip = False
                continue

            # Skip boilerplate regardless of section
            if _is_skip_line(line):
                continue

            tag = "[SKIPPED]" if current_is_skip else f"[{current_label}]"
            output.append(f"{tag}  {line}")

    return output


def main():
    samples_dir = Path(__file__).parent / "samples"
    output_dir  = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    out_file = output_dir / "equipment_lines.txt"

    pdfs = sorted(p for p in samples_dir.iterdir()
                  if p.is_file() and p.suffix.lower() == ".pdf")

    if not pdfs:
        print("No PDFs found in samples/")
        return

    with out_file.open("w", encoding="utf-8") as f:
        for pdf_path in pdfs:
            print(f"Processing: {pdf_path.name}")
            f.write(f"\n{'=' * 80}\n")
            f.write(f"FILE: {pdf_path.name}\n")
            f.write(f"{'=' * 80}\n\n")

            lines = dump_pdf(pdf_path)
            if lines:
                f.write("\n".join(lines))
                f.write("\n")
            else:
                f.write("(no content lines extracted)\n")

    print(f"\nDone: {out_file}")


if __name__ == "__main__":
    main()
