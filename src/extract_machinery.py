import re


ENGINE_LABELS = ["main engines", "main engine", "engines", "engine"]
GENERATOR_LABELS = ["main generators", "main generator", "generators", "generator", "gensets", "genset"]

KNOWN_ENGINE_MAKES = [
    "Caterpillar",
    "MTU",
    "MAN",
    "Volvo Penta",
    "Cummins",
    "Detroit Diesel",
    "Yanmar",
    "Deutz",
    "Scania",
    "Perkins",
    "Mitsubishi",
    "Baudouin",
    "Nanni",
    "Iveco",
    "Isuzu",
    "John Deere",
]

KNOWN_GENERATOR_MAKES = [
    "Kohler",
    "Northern Lights",
    "Onan",
    "Fischer Panda",
    "Cummins",
    "Caterpillar",
    "John Deere",
    "Lugger",
    "Perkins",
    "Volvo Penta",
    "Mercedes Benz",
    "Mercedes-Benz",
    "MTU",
    "MAN",
    "Scania",
    "Baudouin",
    "Deutz",
    "Mitsubishi",
    "Yanmar",
    "Westerbeke",
    "Beta Marine",
    "Nanni",
    "Kubota",
    "Vetus",
    "Stamford",
    "Leroy Somer",
    "Mecc Alte",
    "ABB",
    "Rolls Royce",
    "Rolls-Royce",
    "GE",
    "Wartsila",
    "Wärtsilä",
]

TYPE_KEYWORDS = [
    "Inboard",
    "Outboard",
    "IPS",
    "Jet",
    "Electric",
    "Hybrid",
]

FUEL_KEYWORDS = [
    "Diesel",
    "Gasoline",
    "Petrol",
    "Electric",
    "Hybrid",
]

LOCATION_KEYWORDS = [
    "Port Engine Room",
    "Starboard Engine Room",
    "Engine Room",
    "Port",
    "Starboard",
    "Centerline",
    "Forward",
    "Aft",
]

DATE_PATTERNS = [
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    r"\b\d{1,2}-\d{1,2}-\d{2,4}\b",
    r"\b\d{1,2}/\d{4}\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
]


def clean_text(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("′", "'").replace("″", '"')
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def strip_service_phrases(text: str) -> str:
    if not text:
        return text

    text = clean_text(text)

    patterns = [
        r"(?i)\b(?:last\s+)?serviced\b\s*(?:on\s*)?(?:\d{4}|\d{1,2}/\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4})?",
        r"(?i)(?:\d{4}|\d{1,2}/\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4})\s+\bserviced\b",
    ]

    for pattern in patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\(\s*serviced[^)]*\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,;:.])", r"\1", text)
    return text.strip(" ,;:-")


def format_quantity_prefix(text: str) -> str:
    value = str(text or "").strip()

    # Convert start-of-line quantity formats like:
    # 1 x Item
    # 2x Item
    # 3 X Item
    match = re.match(r"^(\d+)\s*[xX]\s+(.*)$", value)
    if match:
        qty = match.group(1)
        rest = match.group(2).strip()
        return f"({qty}) {rest}"

    return value



def normalize_quantity_prefix(text: str) -> str:
    if not text:
        return text

    # (2x) generators -> (2) generators
    text = re.sub(r"\(\s*(\d+)\s*[xX]\s*\)\s*(?=[A-Za-z])", r"(\1) ", text)

    # 2x generators -> (2) generators
    text = re.sub(r"\b(\d+)\s*[xX]\s+(?=[A-Za-z])", r"(\1) ", text)

    # 2xGenerators -> (2) Generators
    text = re.sub(r"\b(\d+)\s*[xX](?=[A-Za-z])", r"(\1) ", text)

    return clean_text(text)


def line_has_equipment_label(line: str, labels: list[str]) -> bool:
    lower = line.lower()
    for label in labels:
        # Standard format: "Main Engines: ..." or "Engines - ..."
        if re.search(rf"\b{re.escape(label)}\b\s*[:\-]", lower):
            return True
        # No-colon format: multi-word label at start of line AND line contains a digit
        # e.g. "MAIN ENGINES 2 x Caterpillar 3516B" or "Main Engine John Deere 6068SFM50"
        # Single-word labels excluded to avoid "ENGINE HOURS" etc.
        if (len(label.split()) > 1 and
                re.match(rf"^{re.escape(label)}\s+\S", lower) and
                re.search(r"\d", lower)):
            return True
    return False


def looks_like_new_label(line: str) -> bool:
    return bool(re.match(r"^[A-Z][A-Za-z0-9/&() \-]{2,60}:\s*", line))


def collect_equipment_blocks(lines: list[str], labels: list[str]) -> list[str]:
    blocks = []

    for i, raw_line in enumerate(lines):
        line = clean_text(raw_line)
        if not line:
            continue

        if line_has_equipment_label(line, labels):
            parts = [line]

            for j in range(i + 1, min(i + 3, len(lines))):
                nxt = clean_text(lines[j])
                if not nxt:
                    continue
                if looks_like_new_label(nxt):
                    break
                parts.append(nxt)

            blocks.append(" ".join(parts))

    return blocks


def detect_count(text: str) -> int:
    lower = text.lower()

    # "2x", "2 x", "(2x)" etc.
    match = re.search(r"\(?([2-4])\s*x\)?", lower)
    if match:
        return int(match.group(1))

    if "twin" in lower:
        return 2
    if "triple" in lower:
        return 3
    if "quad" in lower:
        return 4
    if "single" in lower:
        return 1

    # Standalone count before a word: "2 MAN", "3 Caterpillar" etc.
    match = re.search(r"\b([2-4])\s+[a-z]", lower)
    if match:
        return int(match.group(1))

    return 1


def find_make(text: str, known_makes: list[str]) -> str:
    for make in sorted(known_makes, key=len, reverse=True):
        if re.search(rf"\b{re.escape(make)}\b", text, flags=re.IGNORECASE):
            return make
    return ""


_MODEL_LABEL_WORDS = {"model", "make", "type", "output", "hp", "kw", "kva", "fuel", "hours"}

def find_model(text: str, make: str) -> str:
    if make:
        match = re.search(
            rf"{re.escape(make)}[\s,/-]+([A-Z0-9][A-Z0-9\-/. ]{{1,40}})",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            candidate = match.group(1).strip(" ,/")

            # If the make is immediately followed by a label word like "Model:"
            # (e.g. "Caterpillar Model: C32"), skip to the fallback below
            if candidate.rstrip(": ").lower() in _MODEL_LABEL_WORDS:
                candidate = ""

            # Skip count-prefix candidates like "1x Marine" or "2x Something"
            if candidate and re.match(r'^\d+x\s', candidate, flags=re.IGNORECASE):
                candidate = ""

            if candidate:
                candidate = re.split(
                    r"\b\d+(?:\.\d+)?\s*(?:HP|KW|KVA)\b|"
                    r"\b(?:HP|KW|KVA|Diesel|Gasoline|Petrol|Inboard|Outboard|"
                    r"hrs?|hours?|Port|Starboard|generator|generators|genset|gensets|"
                    r"engine|engines|marine|for|with|range)\b",
                    candidate,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0].strip(" ,/")

                words = candidate.split()
                if len(words) > 3:
                    candidate = " ".join(words[:3])

                # Strip trailing standalone numbers (e.g. "3516B 2" from "3516B 2,447HP")
                candidate = re.sub(r'(\s+\d+)+$', '', candidate).strip(" ,/")

                if candidate and len(candidate) <= 30:
                    return candidate

    fallback = re.search(r"\b([A-Z]{1,4}\d{1,4}[A-Z0-9\-]*)\b", text)
    return fallback.group(1) if fallback else ""


def find_type(text: str) -> str:
    for value in TYPE_KEYWORDS:
        if re.search(rf"\b{re.escape(value)}\b", text, flags=re.IGNORECASE):
            return value
    return ""


def find_fuel_type(text: str) -> str:
    for value in FUEL_KEYWORDS:
        if re.search(rf"\b{re.escape(value)}\b", text, flags=re.IGNORECASE):
            return value
    return ""


def rule_flag(rule_name: str, message: str, line: str = "") -> None:
    if line:
        print(f"[RULE FLAG] {rule_name}: {message} | LINE: {line}")
    else:
        print(f"[RULE FLAG] {rule_name}: {message}")


def find_engine_output_hp(text: str) -> str:
    # Include optional thousands-separator: "2,447HP" → "2447"
    matches = re.findall(r"\b(\d[\d,]*(?:\.\d+)?)\s*(HP|KW|KVA)\b", text, flags=re.IGNORECASE)
    matches = [(v.replace(",", ""), u) for v, u in matches]

    if not matches:
        return ""

    # prefer HP for engines
    for value, unit in matches:
        if unit.upper() == "HP":
            return value

    # rare case: engine output given in KW/KVA
    value, unit = matches[0]
    rule_flag(
        "ENGINE_OUTPUT_NON_HP",
        f"Engine output found in {unit.upper()} instead of HP; keeping numeric value {value}",
        text
    )
    return value


def find_generator_output(text: str) -> str:
    matches = re.findall(r"\b(\d+(?:\.\d+)?)\s*(KVA|KWA|KW)\b", text, flags=re.IGNORECASE)

    if not matches:
        return ""

    # prefer KW / KVA for generators
    for value, unit in matches:
        if unit.upper() in {"KW", "KVA", "KWA"}:
            return value

    # rare case: generator output given in HP
    value, unit = matches[0]
    rule_flag(
        "GENERATOR_OUTPUT_IN_HP",
        f"Generator output found in {unit.upper()} instead of KW/KVA; keeping numeric value {value}",
        text
    )
    return value


def find_hours(text: str) -> list[str]:
    matches = re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:hrs?|hours?)\b", text, flags=re.IGNORECASE)
    deduped = []
    for item in matches:
        if item not in deduped:
            deduped.append(item)
    return deduped


def find_dates(text: str) -> list[str]:
    matches = []
    for pattern in DATE_PATTERNS:
        found = re.findall(pattern, text, flags=re.IGNORECASE)
        for item in found:
            if item not in matches:
                matches.append(item)
    return matches


def find_location(text: str) -> str:
    for value in LOCATION_KEYWORDS:
        if re.search(rf"\b{re.escape(value)}\b", text, flags=re.IGNORECASE):
            return value
    return ""


def build_shared_equipment_data(blocks: list[str], known_makes: list[str], is_engine: bool) -> dict:
    shared = {
        "COUNT": 1,
        "MAKE": "",
        "MODEL": "",
        "TYPE": "",
        "FUEL_TYPE": "",
        "OUTPUT": "",
        "HOURS": [],
        "DATES": [],
        "LOCATION": "",
    }

    for block in blocks:
        clean_block = strip_service_phrases(block)

        shared["COUNT"] = max(shared["COUNT"], detect_count(clean_block))

        if not shared["MAKE"]:
            shared["MAKE"] = find_make(clean_block, known_makes)

        if not shared["MODEL"]:
            shared["MODEL"] = find_model(clean_block, shared["MAKE"])

        if not shared["TYPE"]:
            shared["TYPE"] = find_type(clean_block)

        if not shared["FUEL_TYPE"]:
            shared["FUEL_TYPE"] = find_fuel_type(clean_block)

        if not shared["OUTPUT"]:
            shared["OUTPUT"] = find_engine_output_hp(clean_block) if is_engine else find_generator_output(clean_block)

        if not shared["LOCATION"]:
            shared["LOCATION"] = find_location(clean_block)

        for value in find_hours(clean_block):
            if value not in shared["HOURS"]:
                shared["HOURS"].append(value)

        for value in find_dates(clean_block):
            if value not in shared["DATES"]:
                shared["DATES"].append(value)

    return shared

def strip_hours_tokens(text: str) -> str:
    return re.sub(
        r"\b\d+(?:[.,]\d+)?\s*(?:hrs?|hours?)\b",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def clean_model_candidate(value: str) -> str:
    if not value:
        return ""

    value = str(value).strip()

    # remove any embedded hours token like 1150hrs / 1150 hrs
    value = re.sub(
        r"\b\d+(?:[.,]\d+)?\s*(?:hrs?|hours?)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )

    # if hrs/hour wording still remains, reject it as a model
    if re.search(r"\b(?:hrs?|hours?)\b", value, flags=re.IGNORECASE):
        return ""

    value = re.sub(r"^[\s,/\-:;]+|[\s,/\-:;]+$", "", value).strip()
    return value


def flatten_equipment(shared: dict, prefix: str, max_items: int, output_key: str) -> dict:
    results = {}
    count = min(shared["COUNT"], max_items)

    for idx in range(1, count + 1):
        results[f"{prefix}_{idx}_MAKE"] = shared["MAKE"]
        results[f"{prefix}_{idx}_MODEL"] = clean_model_candidate(shared["MODEL"])
        results[f"{prefix}_{idx}_TYPE"] = shared["TYPE"]
        results[f"{prefix}_{idx}_FUEL_TYPE"] = shared["FUEL_TYPE"]
        results[f"{prefix}_{idx}_{output_key}"] = shared["OUTPUT"]
        results[f"{prefix}_{idx}_LOCATION"] = shared["LOCATION"]

        if len(shared["DATES"]) >= idx:
            date_value = shared["DATES"][idx - 1]
        elif len(shared["DATES"]) == 1:
            date_value = shared["DATES"][0]
        else:
            date_value = ""

        if date_value:
            if len(shared["HOURS"]) >= idx:
                hours_value = shared["HOURS"][idx - 1]
            elif len(shared["HOURS"]) == 1:
                hours_value = shared["HOURS"][0]
            else:
                hours_value = ""
        else:
            hours_value = ""

        results[f"{prefix}_{idx}_HOURS"] = hours_value
        results[f"{prefix}_{idx}_DATE"] = date_value

    return results


def extract_machinery_from_lines(lines: list[str]) -> dict:
    results = {}

    engine_blocks = collect_equipment_blocks(lines, ENGINE_LABELS)
    if engine_blocks:
        engine_shared = build_shared_equipment_data(engine_blocks, KNOWN_ENGINE_MAKES, is_engine=True)
        results.update(flatten_equipment(engine_shared, "ENGINE", 4, "OUTPUT_HP"))

    generator_blocks = collect_equipment_blocks(lines, GENERATOR_LABELS)
    if generator_blocks:
        generator_shared = build_shared_equipment_data(generator_blocks, KNOWN_GENERATOR_MAKES, is_engine=False)
        results.update(flatten_equipment(generator_shared, "GENERATOR", 4, "OUTPUT"))

    results.update(extract_machinery_fields_from_lines(lines))

    # Fallback: explicit "Engine model: X" or "Engine make: X" labels in the PDF
    # (e.g. Atlantis: "Engine model: MAN C V12")
    _engine_model_patterns = [
        r"engine\s+model\s*[:\-]\s*(.+)$",
        r"engine\s+make\s*[:\-]\s*(.+)$",
    ]
    for line in lines:
        if not results.get("ENGINE_1_MODEL"):
            for pat in _engine_model_patterns:
                m = re.search(pat, line, flags=re.IGNORECASE)
                if m:
                    raw = m.group(1).strip()
                    make = results.get("ENGINE_1_MAKE", "")
                    model = find_model(raw, make) if make else ""
                    if model:
                        results["ENGINE_1_MODEL"] = model
                    break

    for i in range(1, 5):
        hours_key = f"ENGINE_{i}_HOURS"
        date_key = f"ENGINE_{i}_DATE"

    if str(results.get(hours_key, "")).strip() and not str(results.get(date_key, "")).strip():
            results[hours_key] = ""

    return results
MACHINERY_FIELD_ALIASES = {
    "STABILIZER": [
        "stabilisers details",
        "stabilizer details",
        "stabiliser details",
        "stabilisers make",
        "stabilizer make",
        "stabilisers manufacturer",
        "stabilizer manufacturer",
        "stabilizers",
        "stabilisers",
        "stabilizer",
        "stabiliser",
        "fins",
    ],
    "STABILIZER_TYPE": [
        "stabilizer type",
        "stabiliser type",
        "stabilizer system",
        "stabiliser system",
    ],
    "STABILIZER_SPEED": [
        "stabilizer speed",
        "stabiliser speed",
        "zero speed stabilizers",
        "zero speed stabilisers",
    ],
    "BOW_THRUSTER": [
        "bow thruster",
        "bowthruster",
    ],
    "STERN_THRUSTER": [
        "stern thruster",
        "sternthruster",
    ],
    "STEERING": [
        "steering",
    ],
    "SHAFTS_PROPELLERS": [
        "shafts",
        "shafts/propellers",
        "shafts & propellers",
        "propellers",
    ],
    "SHORE_POWER": [
        "shore power",
    ],
    "GEARBOX": [
        "gearbox",
        "gear box",
        "transmission",
    ],
}

def normalize_equipment_text(text: str) -> str:
    text = str(text or "").lower()
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def line_contains_alias(text: str, aliases: list[str]) -> bool:
    normalized = normalize_equipment_text(text)

    for alias in aliases:
        alias_norm = normalize_equipment_text(alias)
        if alias_norm in normalized:
            return True

    return False


def extract_full_line_for_alias(lines, aliases: list[str]) -> str:
    sorted_aliases = sorted(aliases, key=len, reverse=True)
    for line in lines:
        text = line.get("text", "") if isinstance(line, dict) else str(line)
        for alias in sorted_aliases:
            value = extract_after_label(text, alias)
            if value:
                return value
    return ""


def get_machinery_aliases(field_name: str) -> list[str]:
    aliases = MACHINERY_FIELD_ALIASES.get(field_name, [])
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
            return clean_text(match.group(1))

    return None


def trim_machinery_value(value: str, current_field: str) -> str:
    all_labels = []

    for aliases in MACHINERY_FIELD_ALIASES.values():
        all_labels.extend(aliases)

    current_aliases = set(MACHINERY_FIELD_ALIASES.get(current_field, []))
    cut_positions = []

    for label in sorted(set(all_labels), key=len, reverse=True):
        if label in current_aliases:
            continue

        pattern = re.compile(rf"\b{re.escape(label)}\b\s*[:\-]", re.IGNORECASE)
        match = pattern.search(value)
        if match:
            cut_positions.append(match.start())

    if cut_positions:
        value = value[:min(cut_positions)]

    value = clean_text(value).strip(" -:")
    return normalize_quantity_prefix(value)


def normalize_stabilizer_speed(value: str) -> str:
    lower = value.lower()

    has_anchor = "at anchor" in lower
    has_underway = "underway" in lower

    if has_anchor and has_underway:
        return "At Anchor & Underway"
    if has_anchor:
        return "At Anchor"
    if has_underway:
        return "Underway"

    if "zero speed" in lower:
        return "At Anchor"

    return clean_text(value)

def extract_stabilizer_speed_from_context(lines: list[str]) -> str:
    stabilizer_aliases = []
    for aliases in MACHINERY_FIELD_ALIASES.values():
        stabilizer_aliases.extend(
            a for a in aliases
            if "stabil" in a or a == "fins"
        )

    for i, raw_line in enumerate(lines):
        line = clean_text(raw_line)
        lower_line = line.lower()

        if any(alias in lower_line for alias in stabilizer_aliases):
            context_lines = [line]

            if i > 0:
                context_lines.insert(0, clean_text(lines[i - 1]))
            if i + 1 < len(lines):
                context_lines.append(clean_text(lines[i + 1]))

            context_text = " ".join(context_lines)
            parsed = normalize_stabilizer_speed(context_text)

            if parsed in {"At Anchor", "Underway", "At Anchor & Underway"}:
                return parsed

    return ""

def clean_steering_value(text: str) -> str:
    value = str(text or "").strip()

    # remove service-status words only for steering extraction
    value = re.sub(r"\b(rebuilt|serviced|service|overhauled)\b", "", value, flags=re.IGNORECASE)

    # remove extra punctuation/spaces left behind
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s*([,;/:-])\s*", r" \1 ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,;:/-")

    return value

def normalize_section_text(text: str) -> str:
    text = str(text or "").lower()
    text = text.replace("&", "and")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_electricity_header(text: str) -> bool:
    t = normalize_section_text(text)

    header_starts = [
        "electrical",
        "electrical system",
        "electrical systems",
        "electricity",
    ]

    return any(t.startswith(header) for header in header_starts)

def is_batteries_header(text: str) -> bool:
    t = normalize_section_text(text)

    batteries_headers = [
        "batteries",
        "battery bank",
        "battery banks",
    ]

    return any(
        t.startswith(normalize_section_text(header))
        for header in batteries_headers
    )


def is_battery_chargers_header(text: str) -> bool:
    t = normalize_section_text(text)

    charger_headers = [
        "battery charger",
        "battery chargers",
        "chargers",
    ]

    return any(
        t.startswith(normalize_section_text(header))
        for header in charger_headers
    )


def is_air_conditioning_header(text: str) -> bool:
    t = normalize_section_text(text)

    aircon_headers = [
        "air conditioning",
        "air conditioning system",
        "air conditioning systems",
        "air-conditioning",
        "hvac",
        "chiller",
        "chillers",
    ]

    return any(
        t.startswith(normalize_section_text(header))
        for header in aircon_headers
    )

def extract_air_conditioning_lines(lines) -> list[str]:
    # First try normal section-header extraction
    section_lines = extract_section_lines(lines, is_air_conditioning_header)
    if section_lines:
        return section_lines

    # Fallback: capture any lines mentioning strong aircon indicators
    # Exclude lines that just mention AC in passing (engine room, salon descriptions etc.)
    _AIRCON_EXCLUDE = re.compile(
        r"engine.room|salon|upgraded.to|full.air.cond|opens.to|stateroom|cabin|deck",
        re.IGNORECASE,
    )
    aircon_lines = []

    for line in lines:
        text = line.get("text", "") if isinstance(line, dict) else str(line)
        raw = str(text or "").strip()
        norm = normalize_section_text(raw)

        if not raw:
            continue

        if (
            "btu" in norm
            or "chiller" in norm
            or "chillers" in norm
            or "air conditioning" in norm
            or "air-conditioning" in norm
            or "hvac" in norm
        ):
            if _AIRCON_EXCLUDE.search(raw):
                continue
            aircon_lines.append(raw)

    deduped = []
    for item in aircon_lines:
        if item not in deduped:
            deduped.append(item)

    return deduped


def looks_like_section_header(text: str) -> bool:
    t = normalize_section_text(text)

    known_headers = [
        "air conditioning",
        "battery charger",
        "battery chargers",
        "batteries",
        "electricity",
        "electrical",
        "electrical system",
        "electrical systems",
        "other machinery",
        "machinery",
    ]

    return any(t.startswith(header) for header in known_headers)

MACHINERY_SECTION_HEADERS = [
    "air conditioning",
    "battery charger",
    "battery chargers",
    "batteries",
    "electricity",
    "electrical",
    "electrical system",
    "electrical systems",
    "other machinery",
    "machinery",
    # document-level section headings that signal the AC/battery section has ended
    "auxiliary machinery",
    "antifouling",
    "navigation",
    "fuel and oil",
    "fuel oil",
    "anchoring",
    "anchor",
    "steering system",
    "firefighting",
    "fire fighting",
    "safety",
    "communication",
    "entertainment",
    "accommodation",
    "tender",
    "deck equipment",
    "refit",
]

EQUIPMENT_SECTION_HEADERS = [
    "accommodation",
    "galley and laundry",
    "galley & laundry",
    "communication equipment",
    "communciation equipment",
    "navigation equipment",
    "entertainment equipment",
    "tenders and toys",
    "tenders & toys",
    "deck equipment",
    "rigs and sails",
    "rigs & sails",
    "safety and security equipment",
    "safety & security equipment",
    "safety security and firefighting equipment",
    "safety, security, and firefighting equipment",
    "safety security equipment",
    "refit history",
]

OTHER_STOP_HEADERS = [
    "broker comments",
    "upgrades and refit",
    "refit",
]

def normalize_section_text(text: str) -> str:
    text = str(text or "").lower()
    text = text.replace("&", "and")
    text = text.replace("/", " ")
    text = re.sub(r"[,:;()\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_electricity_header(text: str) -> bool:
    t = normalize_section_text(text)

    electricity_headers = [
        "electrical",
        "electrical system",
        "electrical systems",
        "electricity",
    ]

    return any(
        t.startswith(normalize_section_text(header))
        for header in electricity_headers
    )


def filter_electricity_bullets(bullets: list[str]) -> list[str]:
    filtered = []

    skip_terms = [
        "shore power",
        "generator",
        "generators",
        "generator hours",
        "genset",
        "gensets",
    ]

    for bullet in bullets:
        text = normalize_section_text(bullet)

        if any(term in text for term in skip_terms):
            continue

        filtered.append(bullet)

    return filtered


OTHER_MACHINERY_CATEGORY_ALIASES = {
    "Fuel Filters": [
        "fuel filter",
        "fuel filters",
    ],
    "WCs": [
        "wc",
        "wcs",
        "toilet",
        "toilets",
        "toilet system",
        "toilet systems",
        "head",
        "heads",
        "head system",
        "head systems",
    ],
    "Oil/Water Separator": [
        "oil water separator",
        "oil/water separator",
        "water separator",
        "oily water separator",
    ],
    "Boilers": [
        "boiler",
        "boilers",
        "hot water boiler",
        "water heater",
    ],
    "Black Water Treatment": [
        "black water treatment",
        "blackwater treatment",
        "black water system",
        "blackwater system",
    ],
    "Grey Water Treatment": [
        "grey water treatment",
        "greywater treatment",
        "grey water system",
        "greywater system",
    ],
    "Sewage Treatment": [
        "sewage treatment",
        "sewage treatment plant",
        "sewage system",
        "waste treatment",
    ],
    "Tank Venting": [
        "tank vent",
        "tank venting",
        "venting system",
    ],
    "Air Compressors": [
        "air compressor",
        "air compressors",
        "compressor",
        "compressors",
    ],
    "Elevators": [
        "elevator",
        "elevators",
        "lift",
        "lifts",
    ],
    "Helicopter": [
        "helicopter",
        "helipad",
        "touch and go",
    ],
}


def fill_other_machinery_grouped(section, items, page):
    if not has_value(items):
        return

    editor = section.locator("[data-testid='texteditor-contenteditable-otherMachineryDescription']").first
    editor.click(force=True)

    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")

    list_mode_on = False

    for item in items:
        if not has_value(item):
            continue

        text = str(item).strip()

        if text.startswith("__HEADER__"):
            heading = text.replace("__HEADER__", "", 1).strip()

            if list_mode_on:
                section.locator("[data-testid='toolbar-list-ul']").first.click()
                list_mode_on = False

            if heading:
                page.keyboard.press("Control+B")
                page.keyboard.insert_text(heading)
                page.keyboard.press("Control+B")
                page.keyboard.press("Enter")
        else:
            if not list_mode_on:
                section.locator("[data-testid='toolbar-list-ul']").first.click()
                list_mode_on = True

            page.keyboard.insert_text(text)
            page.keyboard.press("Enter")

    section.locator("[data-testid='texteditor-toolbar-save-button']").first.click()

def line_matches_any_alias(text: str, aliases: list[str]) -> bool:
    """
    Match lines where one of the aliases appears as a LABEL — i.e. at the
    start of the line, optionally followed by a colon, dash, or end-of-string.
    This prevents short words like 'head' matching narrative sentences.
    """
    normalized = normalize_section_text(text)
    for alias in aliases:
        a = re.escape(normalize_section_text(alias))
        if re.match(rf'^{a}(\s*[:\-/]|\s*$|\s+\w)', normalized):
            return True
    return False


def extract_other_machinery_grouped(lines) -> list[str]:
    grouped = []

    for title, aliases in OTHER_MACHINERY_CATEGORY_ALIASES.items():
        matches = []

        for line in lines:
            text = line.get("text", "") if isinstance(line, dict) else str(line)
            text = str(text or "").strip()
            if not text:
                continue

            if line_matches_any_alias(text, aliases):
                if text not in matches:
                    matches.append(text)

        if matches:
            grouped.append(f"__HEADER__{title}")
            grouped.extend(matches)

    deduped = []
    for item in grouped:
        if item not in deduped:
            deduped.append(item)

    return deduped


def looks_like_section_header(text: str) -> bool:
    t = normalize_section_text(text)

    all_headers = (
        MACHINERY_SECTION_HEADERS
        + EQUIPMENT_SECTION_HEADERS
        + OTHER_STOP_HEADERS
    )

    return any(
        t.startswith(normalize_section_text(header))
        for header in all_headers
    )


def clean_bullet_text(text: str) -> str:
    value = str(text or "").strip()

    # Remove bullet marks at the start
    value = re.sub(r"^[•◦▪■\-–—]+\s*", "", value)

    # Tidy spacing
    value = re.sub(r"\s+", " ", value).strip(" ,;")

    # Convert quantity prefix like 1 x / 2x to (1) / (2)
    value = format_quantity_prefix(value)

    return value


def extract_section_lines(lines, header_match_fn):
    section_lines = []
    in_section = False

    for line in lines:
        text = line.get("text", "") if isinstance(line, dict) else str(line)
        text = str(text or "").strip()

        if not text:
            continue

        if header_match_fn(text):
            in_section = True
            continue

        if in_section and looks_like_section_header(text):
            break

        if in_section:
            section_lines.append(text)

    return section_lines


def split_lines_into_bullets(section_lines: list[str]) -> list[str]:
    bullets = []

    for line in section_lines:
        text = str(line or "").strip()
        if not text:
            continue

        # Split lines that already contain bullet symbols
        parts = re.split(r"(?:^|\s)[•◦▪■]\s*", text)
        parts = [clean_bullet_text(p) for p in parts if clean_bullet_text(p)]

        if parts:
            for part in parts:
                bullets.append(f"• {part}")
            continue

        # Dash-start line = one bullet
        if re.match(r"^[\-–—]\s*", text):
            cleaned = clean_bullet_text(text)
            if cleaned:
                bullets.append(f"• {cleaned}")
            continue

        # Otherwise keep whole line as one bullet
        cleaned = clean_bullet_text(text)
        if cleaned:
            bullets.append(f"• {cleaned}")

    deduped = []
    for item in bullets:
        if item not in deduped:
            deduped.append(item)

    return deduped


def extract_machinery_fields_from_lines(lines: list[str]) -> dict:
    results = {}

    fields = [
        "STABILIZER",
        "STABILIZER_TYPE",
        "STABILIZER_SPEED",
        "BOW_THRUSTER",
        "STERN_THRUSTER",
        "STEERING",
        "SHAFTS_PROPELLERS",
        "SHORE_POWER",
        "GEARBOX",
        "HELICOPTER",
        "LIFT_CAPABLE",
        "WHEELCHAIR_ACCESSIBLE",
    ]

    for field_name in fields:
        aliases = get_machinery_aliases(field_name)

        for line in lines:
            if not line.strip():
                continue

            for alias in aliases:
                raw_value = extract_after_label(line, alias)
                if raw_value:
                    trimmed = trim_machinery_value(raw_value, field_name)

                    if field_name == "STABILIZER_SPEED":
                        trimmed = normalize_stabilizer_speed(trimmed)

                    if trimmed:
                        # STABILIZER should be a make/model, not a yes/no or
                        # speed descriptor like "at anchor: Yes"
                        if field_name == "STABILIZER":
                            lower_trim = trimmed.lower()
                            if (lower_trim in ("yes", "no") or
                                    lower_trim.startswith("at anchor") or
                                    lower_trim.startswith("underway") or
                                    lower_trim.startswith("zero speed") or
                                    lower_trim.endswith(": yes") or
                                    lower_trim.endswith(": no")):
                                continue
                        results[field_name] = trimmed
                        break

            if field_name in results:
                break

    if not results.get("STABILIZER_SPEED"):
        context_speed = extract_stabilizer_speed_from_context(lines)
        if context_speed:
            results["STABILIZER_SPEED"] = context_speed

    results["BOW_THRUSTER"] = extract_full_line_for_alias(
        lines,
        ["bow thruster", "bowthruster"]
    ) or results.get("BOW_THRUSTER", "")

    results["STERN_THRUSTER"] = extract_full_line_for_alias(
            lines,
            ["stern thruster", "sternthruster"]
        ) or results.get("STERN_THRUSTER", "")

    raw_steering = extract_full_line_for_alias(
        lines,
        ["steering system", "steering"]
    ) or results.get("STEERING", "")

    results["STEERING"] = clean_steering_value(raw_steering)

    electricity_section_lines = extract_section_lines(lines, is_electricity_header)
    if electricity_section_lines:
        electricity_bullets = split_lines_into_bullets(electricity_section_lines)
        electricity_bullets = filter_electricity_bullets(electricity_bullets)
        results["ELECTRICITY_BULLETS"] = electricity_bullets



    battery_chargers_section_lines = extract_section_lines(lines, is_battery_chargers_header)
    if battery_chargers_section_lines:
        results["BATTERY_CHARGERS_BULLETS"] = split_lines_into_bullets(
            battery_chargers_section_lines
        )

    batteries_section_lines = extract_section_lines(lines, is_batteries_header)
    if batteries_section_lines:
        results["BATTERIES_BULLETS"] = split_lines_into_bullets(
            batteries_section_lines
        )

    air_conditioning_section_lines = extract_air_conditioning_lines(lines)
    if air_conditioning_section_lines:
        results["AIR_CONDITIONING_BULLETS"] = split_lines_into_bullets(
            air_conditioning_section_lines
        )

    other_machinery_grouped = extract_other_machinery_grouped(lines)
    if other_machinery_grouped:
        results["OTHER_MACHINERY_BULLETS"] = other_machinery_grouped

    return results
