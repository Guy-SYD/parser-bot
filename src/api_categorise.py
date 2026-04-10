"""
api_categorise.py

Replaces keyword-based categorize_sections with an OpenAI API call.

API key resolution order:
  1. ANTHROPIC_API_KEY environment variable
  2. config/anthropic_key.txt  (one line, just the key)

Falls back to keyword matching if no key is configured or the API call fails.
"""

import json
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Subcategory display order — must match categorize_sections.py definitions
# so the output is always in the expected order regardless of API response order
# ---------------------------------------------------------------------------
_SUBCATEGORY_ORDER: dict[str, list[str]] = {
    "GALLEY & LAUNDRY EQUIPMENT": [
        "Galley", "Pantry", "Laundry", "Crew Galley", "Other",
    ],
    "COMMUNICATION EQUIPMENT": [
        "STARLINK", "VSAT", "SATCOM A", "SAT-C", "Iridium Satellite Phone",
        "VHF", "Portable VHF", "VHF Radiotelephones", "SSB", "GMDSS", "Navtex",
        "Telephone System", "Intercom", "Guest Phones", "GSM", "Radio", "Other",
    ],
    "NAVIGATION EQUIPMENT": [
        "Radar", "MFD", "Chart Plotter", "GPS", "AIS", "ECDIS", "Gyrocompass",
        "Auto Pilot", "Echo Sounder", "Log", "Wind Instruments", "Magnetic Compass",
        "Navtex", "Weather Fax", "FLIR", "Search Lights", "Rudder Angle Indicator",
        "Ships Computer", "Alarm", "Horn", "UPS", "Other",
    ],
    "ENTERTAINMENT EQUIPMENT": [
        "WiFi", "Audiovisual", "HiFi", "Control Systems", "Other",
    ],
    "TENDERS & TOYS": [
        "Tenders", "Jetskis", "Diving", "Toys", "Other",
    ],
    "DECK EQUIPMENT": [
        "Anchor", "Windlasses & Capstans", "Crane", "Passerelle",
        "Lighting", "Swimming & Water Features", "Other",
    ],
    "SAFETY & SECURITY EQUIPMENT": [
        "Fixed Firefighting System", "Firefighting Equipment", "Gas Detection",
        "Smoke Detection", "Fire Alarm", "MOB Boat", "Life Rafts",
        "Breathing Apparatus", "Lifejackets", "Immersion Suits", "Life Rings",
        "EPIRB", "SART", "Flares And Signals", "Medical Equipment",
        "CCTV", "Monitors", "Ship's Safe", "Doorbell", "Other",
    ],
}


# ---------------------------------------------------------------------------
# API key loading
# ---------------------------------------------------------------------------

def _load_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    key_file = BASE_DIR / "config" / "anthropic_key.txt"
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
        if key:
            return key
    return None


def _load_prompt() -> str:
    prompt_file = BASE_DIR / "src" / "equipment_categorisation_prompt.md"
    return prompt_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Format conversion helpers
# ---------------------------------------------------------------------------

def _api_json_to_structured(
    api_result: dict,
    pdf_name: str = "",
) -> dict[str, list[tuple[str, list[str]]]]:
    """
    Convert API JSON response:
        {"COMMUNICATION EQUIPMENT": {"VHF": ["item1"], ...}, ...}
    to the format input_YIQ.py expects:
        {"COMMUNICATION EQUIPMENT": [("VHF", ["item1"]), ...]}

    Also logs Other items to the feedback system.
    """
    from feedback import log_others

    structured: dict[str, list[tuple[str, list[str]]]] = {}

    for bucket, subcats in api_result.items():
        if not isinstance(subcats, dict):
            continue

        order = _SUBCATEGORY_ORDER.get(bucket, [])
        ordered_subcats: list[tuple[str, list[str]]] = []

        # Collect Other items for feedback logging
        other_items: list[str] = []

        # Sort subcategories in canonical display order; unknowns go last
        seen = set()
        for subcat_name in order:
            if subcat_name in subcats:
                items = [str(i).strip() for i in subcats[subcat_name] if str(i).strip()]
                if items:
                    if subcat_name == "Other":
                        other_items.extend(items)
                    else:
                        ordered_subcats.append((subcat_name, items))
                seen.add(subcat_name)

        # Any subcategory the model returned that isn't in our order list
        for subcat_name, items in subcats.items():
            if subcat_name in seen:
                continue
            items = [str(i).strip() for i in items if str(i).strip()]
            if items:
                other_items.extend(items)  # treat unknown subcats as Other

        # Append Other at the end if there's anything
        if other_items:
            ordered_subcats.append(("Other", other_items))

        if ordered_subcats:
            structured[bucket] = ordered_subcats

    # Log Other items for feedback review
    if pdf_name:
        try:
            log_others(pdf_name, structured)
        except Exception:
            pass  # never let feedback logging break the main flow

    return structured


def _refit_api_to_structured(refit_dict: dict) -> list[tuple[str, list[str]]]:
    """Convert refit year dict from API to list-of-tuples format."""
    result = []
    # Sort years descending (most recent first), General last
    def sort_key(y):
        if y == "General":
            return 0
        try:
            return -int(str(y)[:4])
        except ValueError:
            return 0
    for year in sorted(refit_dict.keys(), key=sort_key):
        items = [str(i).strip() for i in refit_dict[year] if str(i).strip()]
        if items:
            result.append((str(year), items))
    return result


# ---------------------------------------------------------------------------
# Main API call
# ---------------------------------------------------------------------------

def categorise_via_api(
    sections: dict[str, list[str]],
    pdf_name: str = "",
) -> dict[str, list[tuple[str, list[str]]]] | None:
    """
    Send all equipment lines to Claude Haiku for categorisation.

    Returns structured result on success, None on failure (caller should
    fall back to keyword matching).
    """
    api_key = _load_api_key()
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        print("[api_categorise] anthropic package not installed — falling back to keyword matching")
        return None

    # Build the user message: all lines grouped by their source section
    lines_text = []
    for section_key, lines in sections.items():
        if lines:
            lines_text.append(f"[Source: {section_key}]")
            for line in lines:
                lines_text.append(f"  {line}")
    if not lines_text:
        return {}

    user_message = (
        "Categorise the following equipment lines extracted from a yacht brochure PDF. "
        "Return only a JSON object, no other text.\n\n"
        + "\n".join(lines_text)
    )

    system_prompt = _load_prompt()

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as e:
        print(f"[api_categorise] API call failed: {e} — falling back to keyword matching")
        return None

    raw = response.content[0].text.strip()
    # Strip markdown code fences if model wrapped the JSON
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw.strip())

    try:
        api_result = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[api_categorise] JSON parse failed: {e} — falling back to keyword matching")
        return None

    # Handle REFIT HISTORY separately (year-keyed dict, not subcat dict)
    structured = _api_json_to_structured(
        {k: v for k, v in api_result.items() if k != "REFIT HISTORY"},
        pdf_name=pdf_name,
    )
    if "REFIT HISTORY" in api_result and isinstance(api_result["REFIT HISTORY"], dict):
        refit = _refit_api_to_structured(api_result["REFIT HISTORY"])
        if refit:
            structured["REFIT HISTORY"] = refit

    return structured


# ---------------------------------------------------------------------------
# Public entry point — drop-in replacement for categorize_sections()
# ---------------------------------------------------------------------------

def categorise_with_fallback(
    sections: dict[str, list[str]],
    pdf_name: str = "",
) -> dict[str, list[tuple[str, list[str]]]]:
    """
    Try API categorisation first. Fall back to keyword matching if API is
    unavailable or fails. Always returns the same format as categorize_sections().
    """
    result = categorise_via_api(sections, pdf_name=pdf_name)

    if result is not None:
        print("[api_categorise] Categorised via OpenAI API")
        return result

    # Fallback
    from categorize_sections import categorize_sections
    print("[api_categorise] Using keyword matching (no API key or API error)")
    return categorize_sections(sections)
