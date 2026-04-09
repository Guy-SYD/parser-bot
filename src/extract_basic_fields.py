import re
from field_aliases import FIELD_ALIASES


BASIC_FIELDS = [
    "YEAR",
    "REFIT",
    "BUILDER",
    "GT",
    "STATEROOMS",
    "GUESTS",
    "CREW",
    "YACHT_TYPE",
    "YACHT_SUBTYPE",
    "MODEL",
    "HULL_NUMBER",
    "HULL_MATERIAL",
    "HULL_COLOR",
    "HULL_CONFIGURATION",
    "SUPERSTRUCTURE_MATERIAL",
    "RIG_TYPE",
    "BUILD_TYPE",
    "EXTERIOR_DESIGNER",
    "INTERIOR_DESIGNER",
    "REFIT_EXTERIOR_DESIGNER",
    "REFIT_INTERIOR_DESIGNER",
    "NAVAL_ARCHITECT",
    "CONVERSION_YEAR",
    "NET_TONNAGE",
    "DISPLACEMENT_NOTES",
    "FULL_DISPLACEMENT",
    "HALF_LOAD_DISPLACEMENT",
    "LIGHT_LOAD_DISPLACEMENT",
    "IACS_SOCIETY",
    "FLAG",
    "REGISTRY_PORT",
    "IMO",
    "MMSI",
    "COMMERCIAL_COMPLIANCE",
    "HELICOPTER",
    "LIFT_CAPABLE",
    "WHEELCHAIR_ACCESSIBLE",
]

HEADER_EXCLUSIONS = [
    "classifications",
    "classification",
    "class",
    "mca",
    "ism",
    "flag",
    "fuel capacity",
    "water capacity",
    "speed",
    "range",
    "staterooms",
    "sleeps",
    "guests",
    "crew",
    "crew berths",
    "crew quarters",
    "heads",
    "int designer",
    "interior designer",
    "captain",
    "ext designer",
    "exterior designer",
    "builder",
    "year",
    "refit",
    "engines",
    "engine",
    "generators",
    "generator",
    "propulsion",
    "dimensions",
    "performance",
    "tankage",
    "capacities",
]


def clean_value(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -:")


def extract_number(value: str) -> str:
    match = re.search(r"\b\d[\d,]*\b", value)
    return match.group(0).replace(",", "") if match else ""


def extract_yes_no(value: str) -> str:
    lower = value.lower()
    if "yes" in lower:
        return "Yes"
    if "no" in lower:
        return "No"
    return clean_value(value)


def get_aliases(field_name: str) -> list[str]:
    aliases = FIELD_ALIASES.get(field_name, [])
    return sorted(aliases, key=len, reverse=True)


def match_label_in_line(line: str, alias: str) -> str | None:
    escaped = re.escape(alias)
    patterns = [
        # label at start with colon/dash
        rf"^\s*{escaped}\s*[:\-]\s*(.+)$",
        # label at start without colon (e.g. "LOA 51m")
        rf"^\s*{escaped}\s+(.+)$",
        # label mid-line without colon, value starts with a digit
        # e.g. "DIMENSIONS Length O.A. 51m (167ft)"
        rf"(?<!\w){escaped}(?!\w)\s+(\d[^\t]*?)(?:\s{{2,}}|\s+[A-Z]{{3,}}|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if match:
            return clean_value(match.group(1))

    return None


def parse_special_field(field_name: str, raw_value: str) -> str:
    if field_name in {"YEAR", "REFIT", "STATEROOMS", "GUESTS", "CREW", "IMO", "MMSI"}:
        return extract_number(raw_value)

    if field_name == "GT":
        match = re.search(r"\b\d+(?:\.\d+)?\b", raw_value)
        return match.group(0) if match else clean_value(raw_value)

    if field_name == "COMMERCIAL_COMPLIANCE":
        return extract_yes_no(raw_value)

    if field_name == "GUESTS":
        match = re.search(r"(\d+)\s+guests?", raw_value, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    if field_name == "CREW":
        match = re.search(r"(\d+)\s+crew", raw_value, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    if field_name == "STATEROOMS":
        match = re.search(r"(\d+)\s+staterooms?", raw_value, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    if field_name == "YACHT_TYPE":
            return normalize_yacht_type(raw_value)

    return clean_value(raw_value)

def get_all_known_labels() -> list[str]:
    labels = []

    for aliases in FIELD_ALIASES.values():
        labels.extend(aliases)

    labels.extend([
        "mca",
        "ism",
        "heads",
        "location",
        "price",
        "vat paid",
        "duty paid",
        "fuel cap",
        "water cap",
        "tax status",
        "captain cabin",
        "classifications",
        "classification & regulation",
    ])

    return sorted(set(labels), key=len, reverse=True)


ALL_KNOWN_LABELS = get_all_known_labels()


def _build_split_patterns() -> list[tuple[re.Pattern, str]]:
    all_aliases = []
    for aliases in FIELD_ALIASES.values():
        all_aliases.extend(aliases)
    all_aliases = sorted(set(all_aliases), key=len, reverse=True)
    return [
        (re.compile(rf"(?<!^)(?<!\w)({re.escape(alias)})\s*[:\-]", flags=re.IGNORECASE), alias)
        for alias in all_aliases
    ]

_SPLIT_PATTERNS = _build_split_patterns()


def _build_trim_labels() -> list[tuple[re.Pattern, None]]:
    all_labels = []
    for aliases in FIELD_ALIASES.values():
        all_labels.extend(aliases)
    all_labels.extend(HEADER_EXCLUSIONS)
    result = []
    for label in sorted(set(all_labels), key=len, reverse=True):
        p1 = re.compile(rf"\b{re.escape(label)}\b\s*[:\-]", flags=re.IGNORECASE)
        p2 = re.compile(rf"\b{re.escape(label)}\b", flags=re.IGNORECASE)
        result.append((label, p1, p2))
    return result

_TRIM_LABEL_PATTERNS = _build_trim_labels()


def trim_at_next_label(value: str, current_field: str) -> str:
    current_aliases = set(FIELD_ALIASES.get(current_field, []))
    cut_positions = []

    for label, p1, p2 in _TRIM_LABEL_PATTERNS:
        if label in current_aliases:
            continue
        for p in (p1, p2):
            match = p.search(value)
            if match:
                cut_positions.append(match.start())
                break

    if cut_positions:
        value = value[:min(cut_positions)]

    return clean_value(value).strip(" -:")

def extract_after_label(line: str, alias: str) -> str | None:
    escaped = re.escape(alias)

    patterns = [
        # label at start of line with colon/dash separator
        rf"^\s*{escaped}\s*[:\-]\s*(.+)$",

        # label anywhere in line with colon/dash, e.g. "... Crew Berths: 4"
        rf"(?<!\w){escaped}(?!\w)\s*[:\-]\s*(.+)$",

        # fallback for start-of-line labels without colon
        rf"^\s*{escaped}\s+(.+)$",

        # label mid-line without colon, value starts with a digit
        # e.g. "DIMENSIONS Length O.A. 51m (167ft)"
        rf"(?<!\w){escaped}(?!\w)\s+(\d[^\t]*?)(?:\s{2,}|\s+[A-Z]{3,}|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if match:
            return clean_value(match.group(1))

    return None

def split_merged_label_lines(lines: list[str]) -> list[str]:
    split_lines = []

    for raw in lines:
        if not raw:
            continue

        parts = re.split(r"[\r\n]+", str(raw))

        for part in parts:
            part = clean_value(part)
            if not part:
                continue

            working = part

            for pattern, _alias in _SPLIT_PATTERNS:
                working = pattern.sub(r"\n\1: ", working)

            for sub in working.split("\n"):
                sub = clean_value(sub)
                if sub:
                    split_lines.append(sub)

    return split_lines


def extract_basic_fields_from_lines(lines: list[str]) -> dict:
    results = {}
    lines = split_merged_label_lines(lines)
    lines = expand_embedded_lines(lines)    

    for field_name in BASIC_FIELDS:
        aliases = get_aliases(field_name)

        for line in lines:
            if not line.strip():
                continue

            for alias in aliases:
                raw_value = match_label_in_line(line, alias)
                if raw_value:
                    trimmed_value = trim_at_next_label(raw_value, field_name)
                    parsed_value = parse_special_field(field_name, trimmed_value)
                    if parsed_value:
                        results[field_name] = parsed_value
                        break

            if field_name in results:
                break

    # Fallback: scan all lines for "N guests" pattern if GUESTS not yet found
    if "GUESTS" not in results:
        for line in lines:
            m = re.search(r"\b(\d+)\s+guests?\b", line, flags=re.IGNORECASE)
            if m:
                results["GUESTS"] = m.group(1)
                break

    # Fallback: infer YACHT_TYPE from strong type indicators when no labeled field found
    if "YACHT_TYPE" not in results:
        _motor_patterns = [
            r"\bm/y\b",
            r"\bmotor\s+yacht\b",
            r"\bmotoryacht\b",
            r"\bmotor\s*boat\b",
            r"\bmotorboat\b",
            r"\bpower\s*boat\b",
            r"\bpowerboat\b",
        ]
        _sailing_patterns = [
            r"\bs/y\b",
            r"\bsailing\s+yachts?\b",
            r"\bsail\s+yacht\b",
            r"\bketch\b",
            r"\bsloop\b",
            r"\byawl\b",
            r"\bschooner\b",
            r"\bbrigantine\b",
            r"\bcutter\b",
        ]
        motor_score = 0
        sailing_score = 0
        for line in lines:
            low = line.lower()
            for pat in _motor_patterns:
                if re.search(pat, low):
                    motor_score += 1
                    break
            for pat in _sailing_patterns:
                if re.search(pat, low):
                    sailing_score += 1
                    break

        if motor_score > sailing_score:
            results["YACHT_TYPE"] = "Motor"
        elif sailing_score > motor_score:
            results["YACHT_TYPE"] = "Sailing"

    return results

def expand_embedded_lines(lines: list[str]) -> list[str]:
    expanded = []

    for raw in lines:
        if not raw:
            continue

        for part in re.split(r"[\r\n]+", str(raw)):
            part = clean_value(part)
            if part:
                expanded.append(part)

    return expanded

def normalize_yacht_type(value: str) -> str:
    lower = value.lower()

    if "motor" in lower:
        return "Motor"
    if "sailing" in lower or "sail" in lower:
        return "Sailing"
    if any(w in lower for w in ("diesel", "power", "screw", "twin engine", "motor yacht")):
        return "Motor"

    return ""
