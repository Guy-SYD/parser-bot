import re
from field_aliases import FIELD_ALIASES


DIMENSION_FIELDS = {
    "LOA": ("LOA_FT", "LOA_IN", "LOA_M"),
    "BEAM": ("BEAM_FT", "BEAM_IN", "BEAM_M"),
    "MAX_DRAFT": ("MAX_DRAFT_FT", "MAX_DRAFT_IN", "MAX_DRAFT_M"),
    "MIN_DRAFT": ("MIN_DRAFT_FT", "MIN_DRAFT_IN", "MIN_DRAFT_M"),
}

from decimal import Decimal, ROUND_HALF_UP


def to_decimal(value: str) -> Decimal | None:
    if value is None:
        return None

    text = str(value).strip().replace(",", "")
    if not text:
        return None

    try:
        return Decimal(text)
    except Exception:
        return None


def round_whole_decimal(number: Decimal) -> int:
    return int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def meters_to_feet_inches(meters_str: str) -> tuple[str, str]:
    meters = to_decimal(meters_str)
    if meters is None:
        return "", ""

    total_inches = meters * Decimal("39.37007874")
    total_inches_rounded = round_whole_decimal(total_inches)

    feet = total_inches_rounded // 12
    inches = total_inches_rounded % 12

    return str(feet), str(inches)


def feet_inches_to_meters(feet_str: str, inches_str: str) -> str:
    feet = to_decimal(feet_str) or Decimal("0")
    inches = to_decimal(inches_str) or Decimal("0")

    total_inches = (feet * Decimal("12")) + inches
    meters = total_inches * Decimal("0.0254")

    return str(meters.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def backfill_dimension_pair(results: dict, ft_key: str, in_key: str, m_key: str) -> None:
    ft_val = results.get(ft_key, "")
    in_val = results.get(in_key, "")
    m_val = results.get(m_key, "")

    has_imperial = bool(ft_val or in_val)
    has_metric = bool(m_val)

    # metric present, imperial missing
    if has_metric and not has_imperial:
        ft, inches = meters_to_feet_inches(m_val)
        results[ft_key] = ft
        results[in_key] = inches

    # imperial present, metric missing
    elif has_imperial and not has_metric:
        results[m_key] = feet_inches_to_meters(ft_val, in_val)

def clean_text(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("′", "'").replace("″", '"')
    return re.sub(r"\s+", " ", text).strip()


def get_aliases(field_name: str) -> list[str]:
    aliases = FIELD_ALIASES.get(field_name, [])
    return sorted(aliases, key=len, reverse=True)


def extract_after_label(line: str, alias: str) -> str | None:
    escaped = re.escape(alias)
    patterns = [
        rf"^\s*{escaped}\s*[:\-]\s*(.+)$",
        rf"^\s*{escaped}\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def parse_dimension_value(raw_value: str) -> dict:
    value = clean_text(raw_value)

    result = {
        "ft": "",
        "in": "",
        "m": "",
    }

    # metric like 43.61m or 43.61 m
    m_match = re.search(r"\b(\d+(?:\.\d+)?)\s*m\b", value, flags=re.IGNORECASE)
    if m_match:
        result["m"] = m_match.group(1)

    # imperial like 143' 1" or 143' or 143 ft 1 in
    ft_in_match = re.search(
        r"\b(\d+)\s*(?:'|ft|feet)\s*(?:(\d+)\s*(?:\"|in|inch|inches))?",
        value,
        flags=re.IGNORECASE,
    )
    if ft_in_match:
        result["ft"] = ft_in_match.group(1)
        result["in"] = ft_in_match.group(2) or ""

    return result


def extract_dimensions_from_lines(lines: list[str]) -> dict:
    results = {}

    for field_name, output_keys in DIMENSION_FIELDS.items():
        aliases = get_aliases(field_name)

        for line in lines:
            line = clean_text(line)
            if not line:
                continue

            for alias in aliases:
                raw_value = extract_after_label(line, alias)
                if raw_value:
                    parsed = parse_dimension_value(raw_value)

                    ft_key, in_key, m_key = output_keys
                    if parsed["ft"]:
                        results[ft_key] = parsed["ft"]
                    if parsed["in"]:
                        results[in_key] = parsed["in"]
                    if parsed["m"]:
                        results[m_key] = parsed["m"]
                    break

            if any(k in results for k in output_keys):
                break
        dimension_triples = [
        ("LOA_FT", "LOA_IN", "LOA_M"),
        ("BEAM_FT", "BEAM_IN", "BEAM_M"),
        ("MAX_DRAFT_FT", "MAX_DRAFT_IN", "MAX_DRAFT_M"),
        ("MIN_DRAFT_FT", "MIN_DRAFT_IN", "MIN_DRAFT_M"),
    ]

    for ft_key, in_key, m_key in dimension_triples:
        backfill_dimension_pair(results, ft_key, in_key, m_key)

    

    return results
