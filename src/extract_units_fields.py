import re
from decimal import Decimal, ROUND_HALF_UP
from field_aliases import UNIT_FIELD_ALIASES
from extract_basic_fields import trim_at_next_label, clean_value


UNIT_PATTERNS = {
    "KNOTS": [
        "knots",
        "knot",
        "kn",
        "kts",
    ],
    "NM": [
        "nm",
        "nmi",
        "nautical miles",
        "nautical mile",
    ],
    "LITERS": [
        "l",
        "lt",
        "ltr",
        "litre",
        "litres",
        "liter",
        "liters",
    ],
    "GALLONS": [
        "gal",
        "gals",
        "gallon",
        "gallons",
    ],
}

from decimal import Decimal, ROUND_HALF_UP


def round_whole_string(value: str) -> str:
    if value is None:
        return ""

    text = str(value).strip().replace(",", "")
    if not text:
        return ""

    try:
        number = Decimal(text)
        return str(int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    except Exception:
        return value


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


def backfill_liters_gallons(results: dict, liters_key: str, gallons_key: str) -> None:
    liters = to_decimal(results.get(liters_key, ""))
    gallons = to_decimal(results.get(gallons_key, ""))

    # liters present, gallons missing
    if liters is not None and not results.get(gallons_key):
        calc_gallons = liters * Decimal("0.2641720524")
        results[gallons_key] = str(
            int(calc_gallons.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        )

    # gallons present, liters missing
    elif gallons is not None and not results.get(liters_key):
        calc_liters = gallons * Decimal("3.785411784")
        results[liters_key] = str(
            int(calc_liters.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        )

def round_whole_string(value: str) -> str:
    if value is None:
        return ""

    text = str(value).strip().replace(",", "")
    if not text:
        return ""

    try:
        number = Decimal(text)
        return str(int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    except Exception:
        return value

def get_aliases(field_name: str) -> list[str]:
    aliases = UNIT_FIELD_ALIASES.get(field_name, [])
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
            return clean_value(match.group(1))

    return None


def extract_metric_and_imperial(value: str) -> tuple[str, str]:
    """
    Returns (liters, gallons)
    """
    liters = ""
    gallons = ""

    l_match = re.search(
        r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(l|lt|ltr|litre|litres|liter|liters)\b",
        value,
        flags=re.IGNORECASE,
    )
    if l_match:
        liters = l_match.group(1).replace(",", "")

    g_match = re.search(
        r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(gal|gals|gallon|gallons)\b",
        value,
        flags=re.IGNORECASE,
    )
    if g_match:
        gallons = g_match.group(1).replace(",", "")

    return liters, gallons


def extract_single_number(value: str) -> str:
    match = re.search(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\b", value)
    return match.group(1).replace(",", "") if match else ""

def to_number(value: str) -> float | None:
    if not value:
        return None

    text = str(value).replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None

    return float(match.group(0))


def rule_flag(rule_name: str, message: str, line: str = "") -> None:
    if line:
        print(f"[RULE FLAG] {rule_name}: {message} | LINE: {line}")
    else:
        print(f"[RULE FLAG] {rule_name}: {message}")


def flag_liters_less_than_gallons(results: dict, liters_key: str, gallons_key: str) -> None:
    liters_val = to_number(results.get(liters_key, ""))
    gallons_val = to_number(results.get(gallons_key, ""))

    if liters_val is not None and gallons_val is not None and liters_val < gallons_val:
        rule_flag(
            "LITERS_LESS_THAN_GALLONS",
            f"{liters_key}={results.get(liters_key, '')} and {gallons_key}={results.get(gallons_key, '')}"
        )


def enforce_range_rules(results: dict) -> None:
    range_keys = ["CRUISE_RANGE", "ECONOMICAL_RANGE", "MAX_RANGE"]
    grouped = {}

    for key in range_keys:
        numeric = to_number(results.get(key, ""))
        if numeric is None:
            continue
        grouped.setdefault(numeric, []).append(key)

    for numeric_value, keys in grouped.items():
        if len(keys) <= 1:
            continue

        # keep CRUISE first if duplicated
        if "CRUISE_RANGE" in keys:
            keep = "CRUISE_RANGE"
        elif "ECONOMICAL_RANGE" in keys:
            keep = "ECONOMICAL_RANGE"
        else:
            keep = keys[0]

        for key in keys:
            if key != keep:
                results[key] = ""

        rule_flag(
            "DUPLICATE_RANGES",
            f"Duplicate range value {numeric_value} found in {keys}; kept {keep}"
        )

def to_number(value: str) -> float | None:
    if not value:
        return None

    text = str(value).replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None

    return float(match.group(0))


def blank_liters_if_higher(results: dict, liters_key: str, gallons_key: str) -> None:
    liters_val = to_number(results.get(liters_key, ""))
    gallons_val = to_number(results.get(gallons_key, ""))

    if liters_val is not None and gallons_val is not None and liters_val < gallons_val:
        results[liters_key] = ""


def blank_duplicate_values(results: dict, ordered_keys: list[str]) -> None:
    seen = set()

    for key in ordered_keys:
        raw = results.get(key, "")
        if not raw:
            continue

        numeric = to_number(raw)
        normalized = str(numeric) if numeric is not None else raw.strip().lower()

        if normalized in seen:
            results[key] = ""
        else:
            seen.add(normalized)


def parse_speed_range_table_row(line: str) -> dict:
    """
    Handles the YATCO-style speed/range/consumption table rows, e.g.:
        "Maximum: 15 knots"
        "Cruising: 12 knots    4000 NM"
        "Economical: 11 knots  170 l/h"

    These rows start with the speed category as the label, which means the
    normal label-matching in parse_speed_line misses them (it looks for the
    category word INSIDE the value, not as the label).
    """
    results = {}

    label_match = re.match(
        r"^\s*(maximum|max|cruising|cruise|economical|economic|economy)\s*[:\s]\s*(.+)$",
        line,
        flags=re.IGNORECASE,
    )
    if not label_match:
        return results

    label = label_match.group(1).lower()
    rest  = label_match.group(2)

    if label in ("maximum", "max"):
        speed_key       = "MAX_SPEED"
        range_key       = "MAX_RANGE"
        consumption_key = None
    elif label in ("cruising", "cruise"):
        speed_key       = "CRUISE_SPEED"
        range_key       = "CRUISE_RANGE"
        consumption_key = "CRUISING_CONSUMPTION_L"
    else:  # economical / economic / economy
        speed_key       = "ECONOMICAL_SPEED"
        range_key       = "ECONOMICAL_RANGE"
        consumption_key = "ECONOMICAL_CONSUMPTION_L"

    # speed value
    speed_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:knots?|kn|kts?)\b", rest, flags=re.IGNORECASE
    )
    if speed_match:
        results[speed_key] = speed_match.group(1)

    # range value (NM present in same cell)
    range_match = re.search(
        r"(\d[\d,]*(?:\.\d+)?)\s*(?:nm|nmi|nautical miles?)\b", rest, flags=re.IGNORECASE
    )
    if range_match:
        results[range_key] = range_match.group(1).replace(",", "")

    # consumption (l/h or lph)
    if consumption_key:
        cons_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:l/h|lph|lit/h|litres?/h|liters?/h)\b",
            rest,
            flags=re.IGNORECASE,
        )
        if cons_match:
            results[consumption_key] = cons_match.group(1)

    return results


def parse_speed_line(line: str) -> dict:
    results = {}
    lower = line.lower()

    if "speed" not in lower and "kn" not in lower and "knot" not in lower:
        return results

    max_match = re.search(r"(?:max|maximum)\s*(\d+(?:\.\d+)?)", line, flags=re.IGNORECASE)
    if max_match:
        results["MAX_SPEED"] = max_match.group(1)

    cruise_match = re.search(r"(?:cruise|cruising)\s*(\d+(?:\.\d+)?)", line, flags=re.IGNORECASE)
    if cruise_match:
        results["CRUISE_SPEED"] = cruise_match.group(1)

    eco_match = re.search(r"(?:economical|economic|eco|economy)\s*(\d+(?:\.\d+)?)", line, flags=re.IGNORECASE)
    if eco_match:
        results["ECONOMICAL_SPEED"] = eco_match.group(1)

    # handles: "15 Max 12 Cruising 11 Economical"
    reverse_max = re.search(r"(\d+(?:\.\d+)?)\s*(?:max|maximum)", line, flags=re.IGNORECASE)
    if reverse_max and "MAX_SPEED" not in results:
        results["MAX_SPEED"] = reverse_max.group(1)

    reverse_cruise = re.search(r"(\d+(?:\.\d+)?)\s*(?:cruise|cruising)", line, flags=re.IGNORECASE)
    if reverse_cruise and "CRUISE_SPEED" not in results:
        results["CRUISE_SPEED"] = reverse_cruise.group(1)

    reverse_eco = re.search(r"(\d+(?:\.\d+)?)\s*(?:economical|economic|eco|economy)", line, flags=re.IGNORECASE)
    if reverse_eco and "ECONOMICAL_SPEED" not in results:
        results["ECONOMICAL_SPEED"] = reverse_eco.group(1)

    return results


def parse_range_line(line: str) -> dict:
    results = {}
    lower = line.lower()

    if "range" not in lower:
        return results

    # reject obvious false positives
    if any(word in lower for word in ["sleeps", "guests", "staterooms", "cabins", "heads", "berths"]):
        rule_flag(
            "RANGE_LINE_REJECTED",
            "Line contains accommodation wording, not a true range line",
            line
        )
        return results

    # These label patterns are unambiguous range fields — extract even without a NM unit.
    # e.g. "Range At Cruise Speed: 4000" — the label guarantees it's a range.
    EXPLICIT_CRUISE_LABELS    = ["cruise range", "cruising range", "range at cruise", "range at cruising speed", "range at cruise speed"]
    EXPLICIT_MAX_LABELS       = ["max range", "maximum range", "range at max speed", "range at maximum speed"]
    EXPLICIT_ECON_LABELS      = ["economical range", "economic range", "range at economical speed", "range at economy speed"]

    is_explicit_cruise = any(x in lower for x in EXPLICIT_CRUISE_LABELS)
    is_explicit_max    = any(x in lower for x in EXPLICIT_MAX_LABELS)
    is_explicit_econ   = any(x in lower for x in EXPLICIT_ECON_LABELS)
    is_explicit        = is_explicit_cruise or is_explicit_max or is_explicit_econ

    # Generic "range" lines (no specific label) still require a NM unit to
    # avoid false positives like "temperature range" or "price range".
    if not is_explicit and not has_range_unit(line):
        rule_flag(
            "RANGE_LINE_REJECTED",
            "Line contains 'range' but no NM/NMI/nautical mile unit and no explicit range label",
            line
        )
        return results

    if is_explicit_max:
        value = extract_single_number(line)
        if value:
            results["MAX_RANGE"] = value

    if is_explicit_cruise:
        value = extract_single_number(line)
        if value:
            results["CRUISE_RANGE"] = value

    if is_explicit_econ:
        value = extract_single_number(line)
        if value:
            results["ECONOMICAL_RANGE"] = value

    # Generic range with NM unit — default to CRUISE_RANGE
    if "MAX_RANGE" not in results and "CRUISE_RANGE" not in results and "ECONOMICAL_RANGE" not in results:
        value = extract_single_number(line)
        if value:
            results["CRUISE_RANGE"] = value
            rule_flag(
                "GENERIC_RANGE_DEFAULTED",
                f"Generic range defaulted to CRUISE_RANGE={value}",
                line
            )

    return results

def extract_capacity_field(lines: list[str], field_name: str, liters_key: str, gallons_key: str) -> dict:
    results = {}
    aliases = get_aliases(field_name)

    for line in lines:
        for alias in aliases:
            raw_value = extract_after_label(line, alias)
            if raw_value:
                trimmed = trim_at_next_label(raw_value, field_name)
                liters, gallons = extract_metric_and_imperial(trimmed)

                if liters:
                    results[liters_key] = liters
                if gallons:
                    results[gallons_key] = gallons


                if results:
                    return results

    return results

def is_label_line(line: str) -> bool:
    return bool(re.match(r"^\s*[A-Z][A-Za-z0-9/&() \-]{2,60}:\s*", line))


def has_range_unit(line: str) -> bool:
    return bool(re.search(r"\b(nm|nmi|nautical mile|nautical miles)\b", line, flags=re.IGNORECASE))


def has_speed_unit(line: str) -> bool:
    return bool(re.search(r"\b(knots|knot|kn|kts)\b", line, flags=re.IGNORECASE))


def extract_units_fields_from_lines(lines: list[str]) -> dict:
    results = {}

    # YATCO table rows first — "Maximum: 15 knots", "Cruising: 12 knots 4000 NM", etc.
    # These are run before the generic speed/range parsers so the labelled table values
    # are preferred over ambiguous unlabelled ones.
    for line in lines:
        parsed = parse_speed_range_table_row(line)
        for k, v in parsed.items():
            if k not in results and v:
                results[k] = v

    # generic speed patterns (handles "15 Max", "Cruising 12", "Speed: Cruising 12 Knots", etc.)
    for line in lines:
        parsed = parse_speed_line(line)
        for k, v in parsed.items():
            if k not in results and v:
                results[k] = v

    # ranges
    for line in lines:
        parsed = parse_range_line(line)
        for k, v in parsed.items():
            if k not in results and v:
                results[k] = v

    # capacities / tankage
    capacity_map = [
        ("FUEL", "FUEL_L", "FUEL_GAL"),
        ("FRESH_WATER", "FRESH_WATER_L", "FRESH_WATER_GAL"),
        ("LUBE_OIL", "LUBE_OIL_L", "LUBE_OIL_GAL"),
        ("BLACK_WATER_HOLDING_TANK", "BLACK_WATER_HOLDING_TANK_L", "BLACK_WATER_HOLDING_TANK_GAL"),
        ("GREY_WATER_HOLDING_TANK", "GREY_WATER_HOLDING_TANK_L", "GREY_WATER_HOLDING_TANK_GAL"),
        ("WASTE_OIL", "WASTE_OIL_L", "WASTE_OIL_GAL"),
        ("CRUISING_CONSUMPTION", "CRUISING_CONSUMPTION_L", "CRUISING_CONSUMPTION_GAL"),
        ("ECONOMICAL_CONSUMPTION", "ECONOMICAL_CONSUMPTION_L", "ECONOMICAL_CONSUMPTION_GAL"),
    ]

    for field_name, liters_key, gallons_key in capacity_map:
        parsed = extract_capacity_field(lines, field_name, liters_key, gallons_key)
        for k, v in parsed.items():
            if k not in results and v:
                results[k] = v
            
    # litres can never be higher than gallons
    quantity_pairs = [
        ("FUEL_L", "FUEL_GAL"),
        ("FRESH_WATER_L", "FRESH_WATER_GAL"),
        ("LUBE_OIL_L", "LUBE_OIL_GAL"),
        ("BLACK_WATER_HOLDING_TANK_L", "BLACK_WATER_HOLDING_TANK_GAL"),
        ("GREY_WATER_HOLDING_TANK_L", "GREY_WATER_HOLDING_TANK_GAL"),
        ("WASTE_OIL_L", "WASTE_OIL_GAL"),
        ("CRUISING_CONSUMPTION_L", "CRUISING_CONSUMPTION_GAL"),
        ("ECONOMICAL_CONSUMPTION_L", "ECONOMICAL_CONSUMPTION_GAL"),
    ]

    for liters_key, gallons_key in quantity_pairs:
        blank_liters_if_higher(results, liters_key, gallons_key)

    # speeds can never be identical
    blank_duplicate_values(results, ["MAX_SPEED", "CRUISE_SPEED", "ECONOMICAL_SPEED"])

    # ranges can never be identical
    # order here keeps ECONOMICAL first, then CRUISE, then MAX
    # so generic MAX_RANGE gets blanked first if duplicated
    blank_duplicate_values(results, ["ECONOMICAL_RANGE", "CRUISE_RANGE", "MAX_RANGE"])

        # flag litres < gallons
    quantity_pairs = [
        ("FUEL_L", "FUEL_GAL"),
        ("FRESH_WATER_L", "FRESH_WATER_GAL"),
        ("LUBE_OIL_L", "LUBE_OIL_GAL"),
        ("BLACK_WATER_HOLDING_TANK_L", "BLACK_WATER_HOLDING_TANK_GAL"),
        ("GREY_WATER_HOLDING_TANK_L", "GREY_WATER_HOLDING_TANK_GAL"),
        ("WASTE_OIL_L", "WASTE_OIL_GAL"),
        ("CRUISING_CONSUMPTION_L", "CRUISING_CONSUMPTION_GAL"),
        ("ECONOMICAL_CONSUMPTION_L", "ECONOMICAL_CONSUMPTION_GAL"),
    ]

    for liters_key, gallons_key in quantity_pairs:
        flag_liters_less_than_gallons(results, liters_key, gallons_key)

    # ranges cannot be identical
    enforce_range_rules(results)

    gallon_keys = [
        "FUEL_GAL",
        "FRESH_WATER_GAL",
        "LUBE_OIL_GAL",
        "BLACK_WATER_HOLDING_TANK_GAL",
        "GREY_WATER_HOLDING_TANK_GAL",
        "WASTE_OIL_GAL",
        "CRUISING_CONSUMPTION_GAL",
        "ECONOMICAL_CONSUMPTION_GAL",
    ]

    for key in gallon_keys:
        if results.get(key):
            results[key] = round_whole_string(results[key])

    # backfill missing litres/gallons pairs
    quantity_pairs = [
        ("FUEL_L", "FUEL_GAL"),
        ("FRESH_WATER_L", "FRESH_WATER_GAL"),
        ("LUBE_OIL_L", "LUBE_OIL_GAL"),
        ("BLACK_WATER_HOLDING_TANK_L", "BLACK_WATER_HOLDING_TANK_GAL"),
        ("GREY_WATER_HOLDING_TANK_L", "GREY_WATER_HOLDING_TANK_GAL"),
        ("WASTE_OIL_L", "WASTE_OIL_GAL"),
        ("CRUISING_CONSUMPTION_L", "CRUISING_CONSUMPTION_GAL"),
        ("ECONOMICAL_CONSUMPTION_L", "ECONOMICAL_CONSUMPTION_GAL"),
    ]

    for liters_key, gallons_key in quantity_pairs:
        backfill_liters_gallons(results, liters_key, gallons_key)

    # gallons must be whole numbers
    gallon_keys = [
        "FUEL_GAL",
        "FRESH_WATER_GAL",
        "LUBE_OIL_GAL",
        "BLACK_WATER_HOLDING_TANK_GAL",
        "GREY_WATER_HOLDING_TANK_GAL",
        "WASTE_OIL_GAL",
        "CRUISING_CONSUMPTION_GAL",
        "ECONOMICAL_CONSUMPTION_GAL",
    ]

    for key in gallon_keys:
        if results.get(key):
            results[key] = round_whole_string(results[key])



    return results
