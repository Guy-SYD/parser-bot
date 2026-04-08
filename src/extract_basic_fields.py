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
    "MODEL",
    "HULL_NUMBER",
    "HULL_MATERIAL",
    "HULL_CONFIGURATION",
    "SUPERSTRUCTURE_MATERIAL",
    "EXTERIOR_DESIGNER",
    "INTERIOR_DESIGNER",
    "NAVAL_ARCHITECT",
    "IACS_SOCIETY",
    "FLAG",
    "REGISTRY_PORT",
    "IMO",
    "MMSI",
    "COMMERCIAL_COMPLIANCE",
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
        rf"^\s*{escaped}\s*[:\-]\s*(.+)$",
        rf"^\s*{escaped}\s+(.+)$",
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


def trim_at_next_label(value: str, current_field: str) -> str:
    all_labels = []

    for aliases in FIELD_ALIASES.values():
        all_labels.extend(aliases)

    all_labels.extend(HEADER_EXCLUSIONS)

    current_aliases = set(FIELD_ALIASES.get(current_field, []))
    cut_positions = []

    for label in sorted(set(all_labels), key=len, reverse=True):
        if label in current_aliases:
            continue

        patterns = [
            rf"\b{re.escape(label)}\b\s*[:\-]",   # normal label form
            rf"\b{re.escape(label)}\b",           # bare header form
        ]

        for pattern in patterns:
            match = re.search(pattern, value, flags=re.IGNORECASE)
            if match:
                cut_positions.append(match.start())
                break

    if cut_positions:
        value = value[:min(cut_positions)]

    return clean_value(value).strip(" -:")

def extract_after_label(line: str, alias: str) -> str | None:
    escaped = re.escape(alias)

    patterns = [
        # label at start of line
        rf"^\s*{escaped}\s*[:\-]\s*(.+)$",

        # label appears later in the line, e.g. "... Crew Berths: 4"
        rf"(?<!\w){escaped}(?!\w)\s*[:\-]\s*(.+)$",

        # fallback for start-of-line labels without colon
        rf"^\s*{escaped}\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if match:
            return clean_value(match.group(1))

    return None

def split_merged_label_lines(lines: list[str]) -> list[str]:
    all_aliases = []

    for aliases in FIELD_ALIASES.values():
        all_aliases.extend(aliases)

    # longest first so "crew berths" wins before "crew"
    all_aliases = sorted(set(all_aliases), key=len, reverse=True)

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

            for alias in all_aliases:
                pattern = re.compile(
                    rf"(?<!^)(?<!\w)({re.escape(alias)})\s*[:\-]",
                    flags=re.IGNORECASE
                )
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

    return ""
