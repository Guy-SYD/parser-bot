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

    # ── Mechanical headings ── skip (filled by the Mechanical tab) ──────────
    "engineering & performance":                    None,
    "engineering and performance":                  None,
    "main machinery":                               None,
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

    # ── Marketing / layout headings ── skip ─────────────────────────────────
    "deck & outdoor living":                        None,
    "deck and outdoor living":                      None,
    "other equipment":                              None,   # just a spa-tub note

    # ── ACCOMMODATION ────────────────────────────────────────────────────────
    "interior accommodations":                      "ACCOMMODATION",
    "interior accommodation":                       "ACCOMMODATION",
    "guest accommodations":                         "ACCOMMODATION",

    # ── GALLEY & LAUNDRY EQUIPMENT ───────────────────────────────────────────
    "galley & laundry equipment":                   "GALLEY & LAUNDRY EQUIPMENT",
    "galley and laundry equipment":                 "GALLEY & LAUNDRY EQUIPMENT",
    "main galley equipment":                        "GALLEY & LAUNDRY EQUIPMENT",
    "crew galley / mess equipment / cooking equipment": "GALLEY & LAUNDRY EQUIPMENT",
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

    # ── TENDERS & TOYS ───────────────────────────────────────────────────────
    "tenders & toys":                               "TENDERS & TOYS",
    "tenders and toys":                             "TENDERS & TOYS",
    "water toys and tenders":                       "TENDERS & TOYS",
    "selection of water toys and tenders":          "TENDERS & TOYS",

    # ── DECK EQUIPMENT ───────────────────────────────────────────────────────
    "deck machinery & equipment":                   "DECK EQUIPMENT",
    "deck machinery and equipment":                 "DECK EQUIPMENT",
    "deck equipment":                               "DECK EQUIPMENT",
    "deck machinery":                               "DECK EQUIPMENT",

    # ── SAFETY & SECURITY EQUIPMENT ─────────────────────────────────────────
    "safety, security, & firefighting equipment":   "SAFETY & SECURITY EQUIPMENT",
    "safety, security, and firefighting equipment": "SAFETY & SECURITY EQUIPMENT",
    "safety & security equipment":                  "SAFETY & SECURITY EQUIPMENT",
    "safety and security equipment":                "SAFETY & SECURITY EQUIPMENT",

    # ── REFIT HISTORY ────────────────────────────────────────────────────────
    "capital improvements":                         "REFIT HISTORY",
    "refit history":                                "REFIT HISTORY",
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
    r"^disclaimer$",
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

    if norm in HEADING_TO_SUBTAB:
        return HEADING_TO_SUBTAB[norm]   # None or subtab key

    # Headings containing a subtab's heading phrase (handles vessel-name prefixes
    # e.g. "Sur La Mer Selection of Water Toys and Tenders")
    for heading, subtab in HEADING_TO_SUBTAB.items():
        if heading and norm.endswith(heading):
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
                # Don't include the heading text itself as content
                continue

            # Not a heading — collect if we're inside an active section
            if isinstance(current, str):
                line = _format_quantities(line)
                key_norm = _normalize(line)
                if key_norm in seen.setdefault(current, set()):
                    continue   # duplicate — skip
                seen[current].add(key_norm)
                sections.setdefault(current, []).append(line)

    return sections
