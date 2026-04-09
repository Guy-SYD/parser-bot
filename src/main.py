from schema import YachtData
from pdf_reader import extract_pages
from extract_basic_fields import extract_basic_fields_from_lines
from extract_dimensions import extract_dimensions_from_lines
from extract_units_fields import extract_units_fields_from_lines
from extract_machinery import extract_machinery_from_lines
from extract_sections import extract_sections_from_pages
from utils import save_json
from decimal import Decimal
from normalization import apply_normalization_rules
import argparse

def blank_if_zero(value):
    if value is None:
        return ""

    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return ""

    try:
        number = Decimal(text.replace(",", ""))
        if number == 0:
            return ""
    except Exception:
        pass

    return value

from pathlib import Path


def pick_input_pdf(explicit_path: str | None = None) -> str:
    """
    Return the PDF to parse.

    If --input is supplied on the command line, use that file.
    Otherwise, fall back to the most-recently-modified PDF in samples/.
    This fallback is kept so you can still just drop a PDF in samples/ and
    run the script with no arguments during quick testing.
    """
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path.resolve()}")
        return str(path)

    sample_dir = Path("samples")
    pdf_files = sorted(
        [p for p in sample_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found in {sample_dir.resolve()}. "
            f"Use --input path/to/file.pdf to specify one explicitly."
        )

    chosen = pdf_files[0]
    if len(pdf_files) > 1:
        print(f"Note: multiple PDFs found in samples/ — using most recent: {chosen.name}")
        print("      To use a specific file, run with: --input samples/yourfile.pdf")

    return str(chosen)


def _apply_extractor_results(yacht: YachtData, results: dict, page_num: int, source: str, conflicts: list):
    """
    Write extractor results onto the yacht object, non-destructively.

    Rules:
    - A field is only set if it currently has no value.
    - Empty/zero values (blank strings, "0") are never written.
    - If a non-empty incoming value conflicts with an already-set value, it is
      logged to `conflicts` so you can see what was found but ignored.

    This means: the FIRST non-empty value found (across all pages and
    all extractors) wins.  Nothing is ever silently erased.
    """
    for key, raw_value in results.items():
        value = blank_if_zero(raw_value)

        if not value:  # skip blank / zero values — never overwrite with nothing
            continue

        if not hasattr(yacht, key):
            continue  # field not in schema yet — silently skip (schema is still growing)

        existing = getattr(yacht, key)
        if isinstance(existing, list):
            # List fields (e.g. *_BULLETS): merge across pages, deduplicate
            if isinstance(value, list):
                merged = list(existing)
                for item in value:
                    if item not in merged:
                        merged.append(item)
                setattr(yacht, key, merged)
        elif existing:
            # Scalar: first non-empty value wins; log if a different value was seen
            if str(existing).strip() != str(value).strip():
                conflicts.append(
                    f"  p{page_num} [{source}] {key}: kept '{existing}', ignored '{value}'"
                )
        else:
            setattr(yacht, key, value)


def main():
    arg_parser = argparse.ArgumentParser(
        description="Parse a yacht spec PDF and write output/result.json"
    )
    arg_parser.add_argument(
        "--input",
        help="Path to a specific PDF file. If omitted, uses the most recent PDF in samples/",
        default=None,
    )
    args = arg_parser.parse_args()

    pdf_path = pick_input_pdf(explicit_path=args.input)
    print(f"Parsing: {pdf_path}")

    pages = extract_pages(pdf_path)
    yacht = YachtData()
    conflicts = []

    # basic_fields is most expensive — run once over all pages combined
    # (split_merged_label_lines is O(lines × aliases); no point repeating per page)
    all_lines = [line for page in pages for line in page["lines"]]
    basic = extract_basic_fields_from_lines(all_lines)
    _apply_extractor_results(yacht, basic, 0, "basic", conflicts)

    for page in pages:
        page_num   = page["page_number"]
        dimensions = extract_dimensions_from_lines(page["lines"])
        units      = extract_units_fields_from_lines(page["lines"])
        machinery  = extract_machinery_from_lines(page["lines"])

        _apply_extractor_results(yacht, dimensions, page_num, "dimensions", conflicts)
        _apply_extractor_results(yacht, units,      page_num, "units",      conflicts)
        _apply_extractor_results(yacht, machinery,  page_num, "machinery",  conflicts)

    if conflicts:
        print(f"\nConflicts found (first value kept \u2014 see below for what was ignored):")
        for line in conflicts:
            print(line.encode("ascii", "replace").decode())
        print()

    normalized_data = apply_normalization_rules(yacht.model_dump())
    sections = extract_sections_from_pages(pages)

    if sections:
        print(f"Equipment sections found: {', '.join(sections.keys())}")
    else:
        print("No equipment sections found in PDF.")

    result = {
        "document": {
            "file": pdf_path,
            "page_count": len(pages),
        },
        "pages": pages,
        "data": normalized_data,
        "sections": sections,
    }

    save_json(result, "output/result.json")
    print("Done. Output saved to output/result.json")


if __name__ == "__main__":
    main()
