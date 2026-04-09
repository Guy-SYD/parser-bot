"""
extract_sections.py

Extracts free-text equipment sections from yacht specification PDFs and maps
them to the Equipment tab subtab keys used in YachtIQ.

How it works
------------
1.  Scan every line of every page looking for known section headings.
2.  When a heading is found, switch the "current section" to its Equipment
    subtab key.
3.  Accumulate following non-heading lines into that section until the next
    heading arrives.
4.  Headings mapped to None are "skip" sections — they belong in other tabs
    (Mechanical, Overview…) so we don't capture their content here.
5.  Content from multiple pages is aggregated under the same section key, so
    "Galley" on page 6 and "Galley & Laundry Equipment" on page 13 both end
    up in the GALLEY & LAUNDRY EQUIPMENT key.

Adding support for a new PDF format
------------------------------------
Add the heading text (lowercase) → subtab key (or None to skip) to
HEADING_TO_SUBTAB below.  The heading text is matched case-insensitively
after collapsing whitespace.
"""

import re

# ---------------------------------------------------------------------------
# Heading → Equipment subtab key map
# ---------------------------------------------------------------------------
# Key   : normalised heading text (lowercase, collapsed spaces)
# Value : Equipment subtab key string  →  collect content under this subtab
#         None                         →  skip (content belongs elsewhere)
#         False / missing              →  not a known heading, treat as content

HEADING_TO_SUBTAB: dict[str, str | None] = {

    # ── Overview / classification headings ── skip ──────────────────────────
    "main characteristics":                         None,
    "comments and noteworthy features at a glance": None,
    "classification & regulation":                  None,
    "classification and regulation":                None,
    "capacities":                                   None,
    "construction":                                 None,
    "overview":                                     None,
    "description":                                  None,
    "specifications":                               None,
    "walkthrough":                                  None,
    "key features":                                 None,
    "broker comments":                              None,
    "disclaimer":                                   None,
    "comments":                                     None,
    "exclusions":                                   None,
    "remarks":                                      None,
    "in summary":                                   None,
    "general arrangement plan":                     None,
    "general arrangement":                          None,
    "for sale - specifications":                    None,
    "for sale":                                     None,

    # ── Mechanical headings ── skip (filled by the Mechanical tab) ──────────
    "engineering & performance":                    None,
    "engineering and performance":                  None,
    "main machinery":                               None,
    "machinery":                                    None,
    "mechanical equipment":                         None,
    "ancillary equipment":                          None,
    "auxiliary machinery & electrical system":      None,
    "auxiliary machinery and electrical system":    None,
    "generators & electricity":                     None,
    "generators and electricity":                   None,
    "auxiliary machinery":                          None,
    "fuel & oil system":                            None,
    "fuel and oil system":                          None,
    "fresh water system":                           None,
    "black & grey water system":                    None,
    "black and grey water system":                  None,
    "ac & ventilation system":                      None,
    "ac and ventilation system":                    None,
    "tank capacities":                              None,
    "speed & range":                                None,
    "speed and range":                              None,
    "performance":                                  None,
    "regulation":                                   None,
    "general":                                      None,
    "remarks":                                      None,

    # ── Marketing / layout headings ── skip ─────────────────────────────────
    "deck & outdoor living":                        None,
    "deck and outdoor living":                      None,
    "other equipment":                              None,

    # ── ACCOMMODATION ── skip (not filling YIQ accommodation tab via parser) ──
    "accommodation":                                None,
    "accommodations":                               None,
    "interior accommodations":                      None,
    "interior accommodation":                       None,
    "guest accommodations":                         None,
    "guest accommodation":                          None,
    "guest accommodation & crew":                   None,
    "guest accommodation and crew":                 None,

    # ── GALLEY & LAUNDRY EQUIPMENT ───────────────────────────────────────────
    "galley & laundry equipment":                   "GALLEY & LAUNDRY EQUIPMENT",
    "galley and laundry equipment":                 "GALLEY & LAUNDRY EQUIPMENT",
    "main galley equipment":                        "GALLEY & LAUNDRY EQUIPMENT",
    "crew galley / mess equipment / cooking equipment": "GALLEY & LAUNDRY EQUIPMENT",
    "domestic appliances, equipment & laundry":     "GALLEY & LAUNDRY EQUIPMENT",
    "domestic appliances and equipment & laundry":  "GALLEY & LAUNDRY EQUIPMENT",
    "domestic appliances":                          "GALLEY & LAUNDRY EQUIPMENT",
    "galley equipment":                             "GALLEY & LAUNDRY EQUIPMENT",
    "crew galley":                                  "GALLEY & LAUNDRY EQUIPMENT",
    "galley":                                       "GALLEY & LAUNDRY EQUIPMENT",

    # ── COMMUNICATION EQUIPMENT ──────────────────────────────────────────────
    "communication systems":                        "COMMUNICATION EQUIPMENT",
    "communication equipment":                      "COMMUNICATION EQUIPMENT",
    "communications":                               "COMMUNICATION EQUIPMENT",

    # ── NAVIGATION EQUIPMENT ────────────────────────────────────────────────
    # "Navigation & Communication Systems" is a combined page heading — we start
    # with navigation and switch to communication when the COMMUNICATION SYSTEMS
    # sub-heading arrives (which is also in this map).
    "navigation & communication systems":           "NAVIGATION EQUIPMENT",
    "navigation and communication systems":         "NAVIGATION EQUIPMENT",
    "navigation systems":                           "NAVIGATION EQUIPMENT",
    "navigation equipment":                         "NAVIGATION EQUIPMENT",

    # ── ENTERTAINMENT EQUIPMENT ──────────────────────────────────────────────
    "entertainment, audio/visual and it systems":   "ENTERTAINMENT EQUIPMENT",
    "entertainment equipment":                      "ENTERTAINMENT EQUIPMENT",
    "entertainment":                                "ENTERTAINMENT EQUIPMENT",
    "audio/visual entertainment systems":           "ENTERTAINMENT EQUIPMENT",
    "audio visual entertainment systems":           "ENTERTAINMENT EQUIPMENT",
    "audio/visual & it systems":                    "ENTERTAINMENT EQUIPMENT",
    "audio/visual and it systems":                  "ENTERTAINMENT EQUIPMENT",
    "audio/visual and entertainment":               "ENTERTAINMENT EQUIPMENT",
    "audio/visual & entertainment":                 "ENTERTAINMENT EQUIPMENT",
    "it & entertainment systems":                   "ENTERTAINMENT EQUIPMENT",
    "it and entertainment systems":                 "ENTERTAINMENT EQUIPMENT",
    "office equipment":                             "ENTERTAINMENT EQUIPMENT",

    # ── TENDERS & TOYS ───────────────────────────────────────────────────────
    "tenders & toys":                               "TENDERS & TOYS",
    "tenders and toys":                             "TENDERS & TOYS",
    "water toys and tenders":                       "TENDERS & TOYS",
    "selection of water toys and tenders":          "TENDERS & TOYS",
    "tenders & watersports equipment":              "TENDERS & TOYS",
    "tenders and watersports equipment":            "TENDERS & TOYS",
    "watersports equipment":                        "TENDERS & TOYS",
    "water sports equipment":                       "TENDERS & TOYS",
    "tenders & water toys":                         "TENDERS & TOYS",
    "tenders and water toys":                       "TENDERS & TOYS",

    # ── DECK EQUIPMENT ───────────────────────────────────────────────────────
    "deck machinery & equipment":                   "DECK EQUIPMENT",
    "deck machinery and equipment":                 "DECK EQUIPMENT",
    "deck equipment":                               "DECK EQUIPMENT",
    "deck machinery":                               "DECK EQUIPMENT",
    "deck amenities":                               "DECK EQUIPMENT",

    # ── SAFETY & SECURITY EQUIPMENT ─────────────────────────────────────────
    "safety, security, & firefighting equipment":   "SAFETY & SECURITY EQUIPMENT",
    "safety, security, and firefighting equipment": "SAFETY & SECURITY EQUIPMENT",
    "safety, security, & fire fighting equipment":  "SAFETY & SECURITY EQUIPMENT",
    "safety, security, and fire fighting equipment":"SAFETY & SECURITY EQUIPMENT",
    "safety & security equipment":                  "SAFETY & SECURITY EQUIPMENT",
    "safety and security equipment":                "SAFETY & SECURITY EQUIPMENT",
    "safety & fire fighting equipment":             "SAFETY & SECURITY EQUIPMENT",
    "safety and fire fighting equipment":           "SAFETY & SECURITY EQUIPMENT",

    # ── REFIT HISTORY ────────────────────────────────────────────────────────
    # "endswith" matching in _classify_line means "2022-23 refit", "2019 refit"
    # etc. all match automatically via the base patterns below.
    "capital improvements":                         "REFIT HISTORY",
    "refit history":                                "REFIT HISTORY",
    "refit":                                        "REFIT HISTORY",
    "vessel status":                                "REFIT HISTORY",
    "recent improvements":                          "REFIT HISTORY",
    "recent upgrades":                              "REFIT HISTORY",
}

# ---------------------------------------------------------------------------
# Lines that should always be skipped regardless of section
# ---------------------------------------------------------------------------
_SKIP_PATTERNS = [
    # Broker boilerplate / disclaimer triggers
    r"not available for sale",
    r"these particulars have been",
    r"we cannot.*guarantee",
    r"we cannot.*be liable",
    r"cannot.*be liable",
    r"without warranty",
    r"subject to contract",
    r"intended as a guide",
    r"general guide to the vessel",
    r"we always advise",
    r"details of this vessel",
    r"buyer should instruct",
    r"offered subject to",
    r"exclusions list",
    r"all owners.*personal effects",
    r"name is nontransferable",
    r"exclusions list available",
    r"particulars believed correct",
    r"particulars are believed",
    r"yachts offered are subject to availability",
    r"errors and omissions",
    r"while every effort",
    r"no responsibility",
    r"shall not be held",
    r"accuracy cannot be",
    r"for information purposes",
    r"specifications subject to change",
    r"right to change",
    r"please verify",
    r"confirm details of concern",
    r"independent survey",
    r"by survey.*inspection",
    r"enquiry of the seller",
    r"purchase contract",
    r"properly reflects",
    r"^disclaimer$",
    r"not contractual",
    r"offered for informational",
    r"information purposed only",
    r"do not make any representation",
    r"legal liability or responsibility",
    r"without written consent from",
    r"powered by tcpdf",
    r"adequacy, validity, reliability",
    r"\|\s*\d+\.\d+m\s*\|",   # page footer: "YACHT | 22.63m | Builder | Year"
    r"completeness or usefulness",
    r"yacht inventory, sales",
    r"subject to changes at any time",
    r"prior sale",
    r"warrant the accuracy",
    r"vessel is offered",
    r"owner may consider",

    # Page number footers
    r"^page\s+\d+\s+of\s+\d+$",
    r"^\d+\s+of\s+\d+$",
    r"^page\s+\d+$",
    # Orphan single numbers (e.g. model number wrapped to next line)
    r"^\d+$",
    # Orphan section-label fragments
    r"^systems$",
    r"^equipment$",
    # Standalone bullet/symbol characters (regular string so Unicode escapes resolve)
    "^[\uf0a8\uf0b7\u2022\u2023\u25e6\u25aa\u25cf\u2219\u00b7\u2013\u2014\u2012?*\-]$",
    # Repeated page headers (BF brochure format)
    r"^for sale\b",
    r"^for sale - specifications$",
]

# Short single-word headings that look like content but should trigger a section
# skip (e.g. photo captions in YATCO brochures).
_ALWAYS_SKIP_HEADINGS = {
    "disclaimer",
    "profile",
    "starboard profile",
    "general arrangement",
    "flybridge",
    "flybridge lounge",
    "flybridge seating",
    "skylounge",
    "skylounge dining",
    "skylounge looking aft",
    "bridge deck helm",
    "bridge deck forward helm",
    "bridge deck seating",
    "main salon",
    "main salon looking aft",
    "main salon looking port",
    "main salon looking aft starboard",
    "main salon looking aft port",
    "main salon entertainment",
    "stairway",
    "twin cabin",
    "guest cabin",
    "lower vip starboard",
    "lower vip port",
    "master cabin",
    "master cabin entryway",
    "master cabin dressing room",
    "master cabin head",
    "head",
    "swim platform",
    "drone profile",
    "main aft deck",
    "main deck stairway",
    "owner's foredeck",
    # Accommodation sub-headings — stop section collection
    "salon",
    "master stateroom",
    "master stateroom head",
    "vip stateroom",
    "vip stateroom head",
    "vip stateroom, forward",
    "vip stateroom, aft",
    "guest stateroom",
    "guest stateroom head",
    "guest stateroom, starboard",
    "guest stateroom, port",
    "guest head",
    "crew cabin",
    "crew quarters",
    "crew stateroom",
    "interior accommodations",
    "interior accommodation",
    "accommodations",
    "accommodation",
    "cockpit/aft deck",
    "cockpit / aft deck",
    "deck/exterior",
    "deck / exterior",
    "main helm",
    "electronics & navigation",
    "electronics and navigation",
    "mechanical/engine room",
    "mechanical / engine room",
    "engine room",
    "key features",
    "comments",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace for comparison."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _format_quantities(line: str) -> str:
    """
    Normalise quantity notation to bracketed form without 'x'.
    Examples:  (2x) → (2)   (3X) → (3)   2x → (2)   2X → (2)
    """
    # Already-bracketed form: (2x) / (2X) → (2)
    line = re.sub(r"\((\d+)[xX]\)", r"(\1)", line)
    # Bare form at word boundary: 2x / 2X → (2)
    line = re.sub(r"\b(\d+)[xX]\b", r"(\1)", line)
    return line


def _is_skip_line(line: str) -> bool:
    lower = line.lower()
    return any(re.search(pat, lower) for pat in _SKIP_PATTERNS)


def _strip_allcaps_label(line: str) -> str:
    """
    Strip an ALL CAPS label prefix from a content line, keeping the value.
    e.g.  'SATCOM Seatel 5009 V-sat system'  →  'Seatel 5009 V-sat system'
          'WATERSPORTS 2 x Jet Skis'          →  '2 x Jet Skis'
    Lines that are entirely label-like (no value after) are returned unchanged.
    """
    words = line.split()
    if len(words) < 2:
        return line

    i = 0
    while i < len(words) and re.match(r"^[A-Z][A-Z0-9&/\']+$", words[i]):
        i += 1

    # Only strip if at least one all-caps word found and value remains
    if 0 < i < len(words):
        return " ".join(words[i:])
    return line


def _merge_continuation_lines(lines: list[str]) -> list[str]:
    """
    Join lines that are continuations of the previous line.

    A line is treated as a continuation when it:
    - starts with a lowercase letter, or
    - starts with a joining word (and, or, with, of, including…), or
    - is a short parenthetical fragment like "(externally)."
    """
    if not lines:
        return lines

    _CONNECTORS = re.compile(
        r"^(and|or|with|of|including|plus|&|/)\b", re.IGNORECASE
    )
    _PARENTHETICAL = re.compile(r"^\(.*\)[.,]?$")

    merged = [lines[0]]

    for line in lines[1:]:
        prev = merged[-1]
        is_continuation = (
            (line and line[0].islower())
            or bool(_CONNECTORS.match(line))
            or bool(_PARENTHETICAL.match(line) and len(line) < 30)
        )
        if is_continuation:
            merged[-1] = prev + " " + line
        else:
            merged.append(line)

    return merged


def _classify_line(line: str):
    """
    Returns:
      str   - a subtab key: start collecting into this section
      None  - a known 'skip' heading: stop collecting until next heading
      False - not a heading: treat as content
    """
    norm = _normalize(line)

    # Too long to be a heading (paragraph content)
    if len(norm) > 90:
        return False

    if norm in _ALWAYS_SKIP_HEADINGS:
        return None   # photo caption / layout heading → skip

    # Short ALL CAPS standalone lines (1-3 words) with no punctuation
    # are typically yacht name headers repeated on each page — skip them.
    raw_stripped = line.strip()
    if (raw_stripped == raw_stripped.upper()
            and len(raw_stripped.split()) <= 3
            and not re.search(r"[:\-&/,]", raw_stripped)
            and len(raw_stripped) > 2
            and raw_stripped not in ("VHF", "AIS", "GPS", "SSB", "UPS")):
        # Only skip if it's not already a known heading
        if norm not in HEADING_TO_SUBTAB:
            return None

    # Strip leading number prefix: "12. comments" or "15 refit" → base heading
    norm_stripped = re.sub(r"^\d+[\.\)\s]\s*", "", norm)

    if norm_stripped in HEADING_TO_SUBTAB:
        return HEADING_TO_SUBTAB[norm_stripped]

    if norm in HEADING_TO_SUBTAB:
        return HEADING_TO_SUBTAB[norm]   # None or subtab key

    # Headings containing a subtab's heading phrase (handles vessel-name prefixes
    # e.g. "Sur La Mer Selection of Water Toys and Tenders" or "2022-23 Refit")
    # Only apply to multi-word headings and lines that don't start with bullet chars.
    _BULLET_CHARS = re.compile(r"^[\uf0a8\uf0b7\u2022\u2023\u25e6\u2013\u2014\?\-\*\•]")
    if not _BULLET_CHARS.match(norm):
        for heading, subtab in HEADING_TO_SUBTAB.items():
            if heading and len(heading.split()) >= 2 and norm.endswith(heading):
                return subtab
        # Single-word year-prefix patterns: "2019 refit", "2022 vessel status" etc.
        for heading, subtab in HEADING_TO_SUBTAB.items():
            if heading and len(heading.split()) == 1 and re.match(r"^\d{4}[\-\–]?\d*\s+" + re.escape(heading) + r"$", norm):
                return subtab

    return False   # not a heading


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_sections_from_pages(pages: list[dict]) -> dict[str, list[str]]:
    """
    Process all PDF pages and return a dict mapping Equipment subtab keys to
    lists of content lines extracted from the PDF.

    Usage::

        sections = extract_sections_from_pages(pages)
        # sections["ACCOMMODATION"] → list of text lines
        # sections["NAVIGATION EQUIPMENT"] → list of text lines
        # ...

    Empty sections are omitted from the result dict.
    """
    sections: dict[str, list[str]] = {}
    # Track seen lines per section to avoid duplicates (normalised for comparison)
    seen: dict[str, set[str]] = {}

    # None  = in a skip section (no collection)
    # False = before the first heading (no collection)
    # str   = active subtab key
    current: str | None | bool = False

    for page in pages:
        for raw_line in page.get("lines", []):
            line = raw_line.strip()
            if not line:
                continue

            if _is_skip_line(line):
                continue

            classification = _classify_line(line)

            if classification is not False:
                # It IS a heading — switch active section
                current = classification
                # For REFIT HISTORY, preserve the heading as a year marker
                if current == "REFIT HISTORY" and re.search(r"\b\d{4}\b", line):
                    marker = line.strip()
                    sections.setdefault(current, []).append(f"__YEAR__{marker}")
                continue

            # Not a heading — collect if we're inside an active section
            if isinstance(current, str):
                line = _format_quantities(line)
                key_norm = _normalize(line)
                if key_norm in seen.setdefault(current, set()):
                    continue   # duplicate — skip
                seen[current].add(key_norm)
                sections.setdefault(current, []).append(line)

    # Merge continuation lines in every section
    for key in sections:
        sections[key] = _merge_continuation_lines(sections[key])

    return sections
