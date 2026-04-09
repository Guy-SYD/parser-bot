"""
categorize_sections.py

Takes raw equipment section lines (from extract_sections) and organises them
into predefined category buckets for each section type.

Returns:  dict[section_key, list[tuple[category_name, list[lines]]]]

Each section becomes a list of (category_name, [lines]) pairs in display order.
Categories with no content are omitted. The special REFIT HISTORY section is
grouped by year rather than by keyword category.
"""

import re
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Deduplication helpers
# ---------------------------------------------------------------------------

def _strip_label_prefix(line: str) -> str:
    """
    Remove a leading 'Label: ' prefix so that
    'Tenders: 16.6 ft Williams 505' and '16.6 ft Williams 505'
    compare as the same content.
    Only strips if the label is ≤ 30 chars (avoids stripping real content).
    """
    m = re.match(r'^[^:]{1,30}:\s+(.+)$', line.strip())
    return m.group(1).strip() if m else line.strip()


def _norm(line: str) -> str:
    return re.sub(r'\s+', ' ', _strip_label_prefix(line).lower())


def _is_near_duplicate(a: str, b: str, threshold: float = 0.65) -> bool:
    """Return True if a and b are substantially the same content."""
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return True
    # One is a substring of the other
    if na in nb or nb in na:
        return True
    # Key words of the shorter overlap heavily with the longer
    short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
    short_words = set(short.split())
    long_words = set(long.split())
    # Ignore very common short words
    stop = {'the', 'a', 'an', 'of', 'and', 'in', 'on', 'at', 'to', 'x', 'ft', 'm'}
    content_words = short_words - stop
    if content_words and len(content_words) >= 2:
        overlap = len(content_words & long_words) / len(content_words)
        if overlap >= 0.75:
            return True
    ratio = SequenceMatcher(None, na, nb).ratio()
    return ratio >= threshold


_BARE_LABEL_RE = re.compile(r'^[^:]{1,30}:\s*$')


def _is_bare_label(line: str) -> bool:
    """Return True for lines like 'Cooking Equipment:' with nothing after the colon."""
    return bool(_BARE_LABEL_RE.match(line.strip()))


def _dedup_bucket(lines: list[str]) -> list[str]:
    """
    Remove near-duplicate lines from a bucket and strip bare sub-header labels
    (e.g. 'Cooking Equipment:', 'Main Laundry Equipment:') that add no value
    once items are already sorted into category buckets.
    When two lines are near-duplicates, keep the longer one (more detail).
    """
    kept: list[str] = []
    for line in lines:
        # Drop bare 'Label:' lines — they're PDF sub-headers, not content
        if _is_bare_label(line):
            continue
        duplicate = False
        for i, existing in enumerate(kept):
            if _is_near_duplicate(line, existing):
                if len(line) > len(existing):
                    kept[i] = line
                duplicate = True
                break
        if not duplicate:
            kept.append(line)
    return kept


# ---------------------------------------------------------------------------
# Category definitions — list of (category_name, [keywords])
# A line is assigned to the first category where any keyword matches.
# The last entry in each list is the catch-all (empty keyword list).
# ---------------------------------------------------------------------------

ACCOMMODATION_CATEGORIES = [
    ("Saloon",              ["saloon", "salon", "sky lounge", "skylounge", "sitting area", "seating area",
                             "lounge", "bar to starboard", "wet bar", "circular bar", "fireplace",
                             "entertainment area", "living area", "tv and surround"]),
    ("Dining",              ["dining", "formal dining", "dinner table", "dining area"]),
    ("Master Stateroom",    ["master", "owner's suite", "owner suite", "full-beam suite", "full beam suite",
                             "master suite", "master cabin", "owners cabin", "owner cabin"]),
    ("VIP Stateroom",       ["vip stateroom", "vip suite", "vip cabin"]),
    ("Guest Staterooms",    ["guest stateroom", "guest suite", "guest cabin", "double stateroom",
                             "twin stateroom", "pullman", "guest accommodation", "guest room",
                             "stateroom on lower", "lower deck stateroom"]),
    ("Staff Accommodation", ["captain", "pilothouse", "pilot house", "bridge deck cabin",
                             "crew", "engineer cabin", "crew mess", "crew area", "crew accommodation",
                             "crew cabin", "crew stateroom", "staff cabin", "staff accommodation"]),
    ("Hallways & Stairways",["hallway", "stairway", "staircase", "landing", "corridor", "passage",
                             "foyer", "formal entry", "entrance", "lobby"]),
    ("Sundeck",             ["sundeck", "sun deck"]),
    ("Other",               []),
]

GALLEY_CATEGORIES = [
    ("Galley",              ["galley", "oven", "fridge", "freezer", "cooking", "dishwasher",
                             "sink", "blender", "mixer", "ice maker", "hob", "induction",
                             "refriger", "combi", "microwave", "pizza", "teppanyaki",
                             "extractor", "macerator", "walk-in fridge", "sub-zero",
                             "pacojet", "vitamix", "kitchenaid", "gaggenau", "miele",
                             "zanussi", "smeg", "kenyon", "bosch", "plancher", "true t-"]),
    ("Pantry",              ["pantry", "wine cellar", "wine cooler", "eurocave",
                             "drinks fridge", "bottle", "beverage"]),
    ("Laundry",             ["laundry", "washing machine", "washer", "dryer", "tumble",
                             "pw6065", "pt 7135"]),
    ("Crew Galley",         ["crew galley", "crew mess"]),
    ("Other",               []),
]

COMMUNICATION_CATEGORIES = [
    ("STARLINK",            ["starlink"]),
    ("VSAT",                ["vsat", "ku-band", "c-band"]),
    ("SATCOM A",            ["satcom a", "inmarsat a", "sailor 250", "sailor 500"]),
    ("SAT-C",               ["sat-c", "inmarsat c", "felcom", "sailor c", "navimail"]),
    ("Iridium Satellite Phone", ["iridium"]),
    ("VHF",                 ["vhf", "uhf"]),
    ("Portable VHF",        ["portable vhf", "handheld vhf"]),
    ("VHF Radiotelephones", ["radiotelephone"]),
    ("SSB",                 ["ssb", "mf/hf", "hf radio", "sailor 5000", "sailor ssb"]),
    ("GMDSS",               ["gmdss"]),
    ("Navtex",              ["navtex"]),
    ("Telephone System",    ["telephone", "pbx", "voip", "open stage", "panasonic kx",
                             "siemens", "dect"]),
    ("Intercom",            ["intercom"]),
    ("Guest Phones",        ["guest phone", "cabin phone", "shore phone"]),
    ("GSM",                 ["gsm", "cellular", "4g", "lte", "mobile broadband"]),
    ("Radio",               ["radio", "thrane", "lars thrane", "meridian"]),
    ("Other",               []),
]

NAVIGATION_CATEGORIES = [
    ("Radar",               ["radar"]),
    ("MFD",                 ["mfd", "mfdbb", "multifunction display", "navnet", "maxsea",
                             "navionics", "garmin gps map", "garmin echomap"]),
    ("Chart Plotter",       ["chart plotter", "chartplotter", "plotter", "chart table"]),
    ("GPS",                 ["gps", "dgps", "gpsmap", "gp-", "gp 1"]),
    ("AIS",                 ["ais", "transponder"]),
    ("ECDIS",               ["ecdis", "electronic chart"]),
    ("Gyrocompass",         ["gyrocompass", "gyro compass", "navigat", "gyro"]),
    ("Auto Pilot",          ["auto pilot", "autopilot", "navipilot", "robertson ap",
                             "simrad ap", "furuno autopilot", "furuno 70"]),
    ("Echo Sounder",        ["echo sounder", "echosounder", "depth sounder", "fe700", "fe 700",
                             "depth finder"]),
    ("Log",                 ["speed log", "distance log", "naviknot", "walker log"]),
    ("Wind Instruments",    ["wind instrument", "wind sensor", "anemometer", "airmar"]),
    ("Magnetic Compass",    ["magnetic compass", "cassens", "plath", "jupiter 180"]),
    ("Navtex",              ["navtex"]),
    ("Weather Fax",         ["weather fax", "weatherfax", "weather station", "barometer", "fax30"]),
    ("FLIR",                ["flir", "thermal camera", "night vision"]),
    ("Search Lights",       ["search light", "searchlight", "spotlight"]),
    ("Rudder Angle Indicator", ["rudder angle", "rudder position", "rudder indicator"]),
    ("Ships Computer",      ["ships computer", "ships printer", "ship computer", "ship printer",
                             "navigation computer"]),
    ("Alarm",               ["watch alarm", "watchkeeper", "navigation alarm"]),
    ("Depth Sounder",       ["depth sounder"]),
    ("Horn",                ["fog horn", "ship horn", "horn button", "air horn"]),
    ("UPS",                 ["ups", "uninterruptible"]),
    ("Other",               []),
]

ENTERTAINMENT_CATEGORIES = [
    ("WiFi",                ["wifi", "wi-fi", "wireless network", "access point", "router",
                             "unifi", "ubiquiti", "internet"]),
    ("Audiovisual",         ["tv", "television", "flat screen", "projector", "cinema", "apple tv",
                             "blu-ray", "bluray", "satellite tv", "foxtel", "hdtv", "oled",
                             "led tv", "display", "oppo", "tvro", "kvh", "sat tv", "sat-tv"]),
    ("HiFi",                ["speaker", "amplifier", "audio", "sound system",
                             "hifi", "hi-fi", "music", "subwoofer", "integra", "denon",
                             "sonos", "alpine", "surround", "bose", "harman", "fusion"]),
    ("Control Systems",     ["crestron", "lutron", "control system", "ipad control",
                             "logitech", "prodigy", "home automation"]),
    ("Other",               []),
]

TENDERS_CATEGORIES = [
    ("Tenders",             ["tender", "dinghy", "rigid", "williams", "zodiac", "novurania",
                             "castoldi", "protender", "jet tender", "rescue tender",
                             "special craft", "15'", "16'", "17'", "18'", "19'", "20'",
                             "5.0m", "5.05m", "5.5m", "6m", "7m", "8m", "limousine"]),
    ("Jetskis",             ["jet ski", "jetski", "waverunner", "wave runner", "yamaha vx",
                             "seadoo", "sea-doo", "stand-up jet"]),
    ("Diving",              ["diving", "dive", "scuba", "compressor", "tanks", "regulator",
                             "wetsuit", "drysuit", "bcd", "fins", "mask", "snorkel"]),
    ("Toys",                ["seabob", "sea bob", "kayak", "paddleboard", "paddle board",
                             "wakeboard", "wake board", "foil", "e-foil", "efoil",
                             "towable", "water ski", "waterski", "scooter", "sea wing",
                             "fliteboard", "iaqua", "flyboard", "inflatable platform",
                             "jungle", "tube", "donut", "banana", "kite", "sup board",
                             "snorkelling", "fishing rod", "fishing"]),
    ("Other",               []),
]

DECK_CATEGORIES = [
    ("Anchor",              ["anchor", " chain", "shackle", "rode", "hhp", "poole", "delta"]),
    ("Windlasses & Capstans",["windlass", "capstan", "winch", "lewmar", "lofrans", "nanni"]),
    ("Crane",               ["crane", "davit", "boom", "lifting", "gantry", "jeremy rogers",
                             "ascon", "opengear"]),
    ("Passerelle",          ["passerelle", "gangway", "boarding", "swim ladder", "swimming ladder",
                             "marquipt", "mediterranean passerelle", "motomar", "opac"]),
    ("Lighting",            ["underwater light", "deck light", "exterior light", "led light",
                             "rope light", "strip light", "floodlight", "flood light",
                             "blue led", "perimeter light"]),
    ("Swimming & Water Features", ["swimming platform", "swim platform", "pool", "jacuzzi",
                                   "hot tub", "deck shower", "transom shower"]),
    ("Other",               []),
]

SAFETY_CATEGORIES = [
    # Safety
    ("Fixed Firefighting System", ["fire suppression", "fixed firefighting", "foam system",
                                   "ultrafog", "technoship", "sprinkler", "halon", "novec"]),
    ("Firefighting Equipment", ["extinguisher", "fire hose", "jet nozzle", "fire suit",
                                "co2", "foam 9", "powder", "fire blanket"]),
    ("Gas Detection",       ["gas detector", "co detector", "carbon monoxide", "lpg detector"]),
    ("Smoke Detection",     ["smoke detector", "smoke alarm", "smoke detection"]),
    ("Fire Alarm",          ["fire alarm", "fire detection", "fire panel", "onyx", "consillium"]),
    ("MOB Boat",            ["mob boat", "man overboard", "rescue boat"]),
    ("Life Rafts",          ["life raft", "liferaft", " raft", "duarry", "survitec",
                             "viking", "10-man", "12-man", "20-man", "iso 9650"]),
    ("Breathing Apparatus", ["eebds", "eepds", "drager", "ocenco", "breathing apparatus",
                             "scba", "self-contained"]),
    ("Lifejackets",         ["lifejacket", "life jacket", "adult lifejacket", "child lifejacket"]),
    ("Immersion Suits",     ["immersion suit", "survival suit", "gumby"]),
    ("Life Rings",          ["lifebuoy", "life ring", "lifering", "buoy with lifeline",
                             "dan buoy", "danbuoy", "buoy with smoke"]),
    ("EPIRB",               ["epirb", "acr global", "jotron epirb"]),
    ("SART",                ["sart", "radar transponder", "jotron sart"]),
    ("Flares And Signals",  ["flare", "parachute flare", "handheld flare", "orange smoke",
                             "smoke signal", "distress signal"]),
    ("Medical Equipment",   ["medical", "oxygen", "first aid", "medaire", "resuscitator",
                             "defibrillator", "aed", "stretcher"]),
    # Security
    ("CCTV",                ["cctv", "security camera", "ip camera", "panasonic cctv"]),
    ("Monitors",            ["monitor", "dell display", "security monitor"]),
    ("Ship's Safe",         ["safe", "ship safe", "ship's safe"]),
    ("Doorbell",            ["doorbell", "door bell", "video doorbell"]),
    ("Other",               []),
]


# ---------------------------------------------------------------------------
# Scoring & assignment
# ---------------------------------------------------------------------------

def _score_line(line: str, keywords: list[str]) -> int:
    lower = line.lower()
    return sum(1 for kw in keywords if kw in lower)


def _categorize_lines(
    lines: list[str],
    categories: list[tuple],
) -> list[tuple[str, list[str]]]:
    """
    Assign each line to the best-matching category, then deduplicate.
    - Within each bucket: near-duplicate lines are collapsed (longer kept).
    - Across buckets: once a line is placed, near-duplicates in other
      buckets are removed, so no content repeats across categories.
    Returns only non-empty categories in definition order.
    """
    cat_names = [c[0] for c in categories]
    catch_all = cat_names[-1]

    buckets: dict[str, list[str]] = {name: [] for name in cat_names}

    for line in lines:
        best_cat = catch_all
        best_score = 0
        for cat_name, keywords in categories:
            if not keywords:
                continue
            score = _score_line(line, keywords)
            if score > best_score:
                best_score = score
                best_cat = cat_name
        buckets[best_cat].append(line)

    # Deduplicate within each bucket
    for name in cat_names:
        buckets[name] = _dedup_bucket(buckets[name])

    # Deduplicate across buckets: track what's already placed
    placed: list[str] = []
    result = []
    for name in cat_names:
        clean = []
        for line in buckets[name]:
            if any(_is_near_duplicate(line, p) for p in placed):
                continue
            clean.append(line)
            placed.append(line)
        if clean:
            result.append((name, clean))

    return result


# ---------------------------------------------------------------------------
# Refit: group by year
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r'^(\d{4}(?:[/\-]\d{2,4})?)[:\s]*$')


def _categorize_refit(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Group refit lines by year label, most recent year first."""
    buckets: dict[str, list[str]] = {}
    order: list[str] = []
    current = "General"

    for line in lines:
        m = _YEAR_RE.match(line.strip())
        if m:
            current = m.group(1).rstrip(':/').strip()
            if current not in buckets:
                buckets[current] = []
                order.append(current)
        else:
            if current not in buckets:
                buckets[current] = []
                order.append(current)
            buckets[current].append(line)

    def _sort_key(label: str) -> int:
        if label == "General":
            return 0
        try:
            return -int(label[:4])
        except ValueError:
            return 0

    sorted_order = sorted(order, key=_sort_key)

    # Dedup within each year bucket and across years (most recent wins)
    placed: list[str] = []
    result = []
    for y in sorted_order:
        clean = _dedup_bucket(buckets[y])
        clean = [l for l in clean if not any(_is_near_duplicate(l, p) for p in placed)]
        placed.extend(clean)
        if clean:
            result.append((y, clean))
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SECTION_MAP: dict[str, tuple] = {
    "ACCOMMODATION":               (ACCOMMODATION_CATEGORIES, False),
    "GALLEY & LAUNDRY EQUIPMENT":  (GALLEY_CATEGORIES,        False),
    "COMMUNICATION EQUIPMENT":     (COMMUNICATION_CATEGORIES, False),
    "NAVIGATION EQUIPMENT":        (NAVIGATION_CATEGORIES,    False),
    "ENTERTAINMENT EQUIPMENT":     (ENTERTAINMENT_CATEGORIES, False),
    "TENDERS & TOYS":              (TENDERS_CATEGORIES,       False),
    "DECK EQUIPMENT":              (DECK_CATEGORIES,          False),
    "SAFETY & SECURITY EQUIPMENT": (SAFETY_CATEGORIES,        False),
    "REFIT HISTORY":               (None,                     True),
}


# ---------------------------------------------------------------------------
# Cross-section routing rules
# Lines in a source section that match ANY keyword here are moved to the
# target section instead. Applied before per-section categorization.
# Format: (source_section, target_section, [keywords])
# ---------------------------------------------------------------------------
_CROSS_ROUTE_RULES: list[tuple[str, str, list[str]]] = [
    # Comms items that land in nav sections (main helm, electronics & nav)
    ("NAVIGATION EQUIPMENT", "COMMUNICATION EQUIPMENT", [
        "vhf", "ssb", "satcom", "sat com", "gmdss", "iridium", "starlink",
        "thrane", "vsat", "felcom", "uhf", "mf/hf", "hf radio", "navtex",
        "telephone", "intercom", "pbx", "wifi", "wi-fi", "internet", "4g", "5g",
        "lte", "gsm", "cellular", "voip", "radio", "sailor rt", "simrad rs",
        "sailor 5000", "kvh u7", "kvh u",
    ]),
    # Entertainment items that land in nav sections (TV at helm, sound system)
    ("NAVIGATION EQUIPMENT", "ENTERTAINMENT EQUIPMENT", [
        " tv ", "television", " screen", "dvd", "blu-ray", "bluray",
        "satellite tv", "apple tv", "sonos", "speaker", "audio",
        "fusion msnrx", "fusion ms",
    ]),
    # Safety items that land in deck sections
    ("DECK EQUIPMENT", "SAFETY & SECURITY EQUIPMENT", [
        "life raft", "liferaft", "epirb", "sart", "flare", "lifejacket",
        "life jacket", "lifebuoy", "life ring", "fire extinguisher",
        "extinguisher", "immersion suit", "survival suit", "smoke alarm",
        "fire alarm", "fire suppression", "co2", "fire hose",
    ]),
    # Entertainment items in deck sections
    ("DECK EQUIPMENT", "ENTERTAINMENT EQUIPMENT", [
        " tv", "television", "flat screen", "led tv", "plasma",
        "speaker", "surround sound", "bose", "sound system",
    ]),
]


def _apply_cross_routing(sections: dict[str, list[str]]) -> dict[str, list[str]]:
    """
    Move lines between section buckets before per-section categorization,
    based on keyword matching. Modifies a copy of the sections dict.
    """
    # Work on copies so we don't mutate the input
    result = {k: list(v) for k, v in sections.items()}

    for src_key, dst_key, keywords in _CROSS_ROUTE_RULES:
        if src_key not in result:
            continue
        stay, move = [], []
        for line in result[src_key]:
            lower = line.lower()
            if any(kw in lower for kw in keywords):
                move.append(line)
            else:
                stay.append(line)
        if move:
            result[src_key] = stay
            result.setdefault(dst_key, []).extend(move)

    return result


def categorize_sections(
    sections: dict[str, list[str]],
) -> dict[str, list[tuple[str, list[str]]]]:
    """
    Takes raw sections dict and returns:
        {section_key: [(category_name, [lines]), ...]}

    Sections not in _SECTION_MAP are passed through with an empty category name.
    """
    # Route lines to their correct section before categorizing
    sections = _apply_cross_routing(sections)

    result: dict[str, list[tuple[str, list[str]]]] = {}

    for key, lines in sections.items():
        if key not in _SECTION_MAP:
            result[key] = [("", lines)]
            continue

        categories, is_refit = _SECTION_MAP[key]

        if is_refit:
            result[key] = _categorize_refit(lines)
        else:
            result[key] = _categorize_lines(lines, categories)

    return result
