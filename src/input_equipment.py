"""
input_equipment.py

Reads the 'sections' key from output/result.json and fills the Equipment tab
subtabs on YachtIQ.io for a given yacht ID.

Usage:
    python src/input_equipment.py --id 447250
    python src/input_equipment.py --id 447250 --input output/result.json

Each subtab with content is:
  1. Clicked to make it active
  2. Cleared (Ctrl+A → Backspace)
  3. Filled line-by-line with keyboard.insert_text / keyboard.press("Enter")
  4. Saved by clicking the save button

If the session is expired or state.json does not exist, the script will
automatically log in using the credentials in Login.txt and save the new
session to auth/state.json before continuing.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
OUTPUT_FILE = PROJECT_DIR / "output" / "result.json"
AUTH_STATE  = PROJECT_DIR / "auth" / "state.json"
LOGIN_FILE  = PROJECT_DIR / "Login.txt"

# ---------------------------------------------------------------------------
# Mapping: sections dict key → Equipment subtab visible label on YachtIQ
# ---------------------------------------------------------------------------
SUBTAB_LABELS = {
    "ACCOMMODATION":               "Accommodation",
    "GALLEY & LAUNDRY EQUIPMENT":  "Galley & Laundry Equipment",
    "COMMUNICATION EQUIPMENT":     "Communication Equipment",
    "NAVIGATION EQUIPMENT":        "Navigation Equipment",
    "ENTERTAINMENT EQUIPMENT":     "Entertainment Equipment",
    "TENDERS & TOYS":              "Tenders & Toys",
    "DECK EQUIPMENT":              "Deck Equipment",
    "SAFETY & SECURITY EQUIPMENT": "Safety & Security Equipment",
    "REFIT HISTORY":               "Refit History",
}


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def load_credentials() -> tuple[str, str]:
    """
    Parse Login.txt and return (email, password).
    Expected format (lines in any order):
        Email: guy.butler@boatyard.com
        PW: K0kIaLG1yFqZltPT
    """
    if not LOGIN_FILE.exists():
        raise FileNotFoundError(f"Login.txt not found at {LOGIN_FILE}")

    text = LOGIN_FILE.read_text(encoding="utf-8")
    email_match = re.search(r"(?i)email\s*:\s*(\S+)", text)
    pw_match    = re.search(r"(?i)(?:pw|password)\s*:\s*(\S+)", text)

    if not email_match or not pw_match:
        raise ValueError(f"Could not parse Email and PW from {LOGIN_FILE}")

    return email_match.group(1).strip(), pw_match.group(1).strip()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def is_on_login_page(page) -> bool:
    """Return True if the YachtIQ 'Welcome / Login to YachtIQ' screen is showing."""
    return page.locator("#btn-login").count() > 0


def do_login(page, context, target_url: str):
    """
    Fill the YachtIQ login form, submit, wait for the app to load, then save
    the updated session to auth/state.json so it is reused next time.
    """
    print("Login page detected — signing in automatically...")
    email, password = load_credentials()

    # Fill email (id="email")
    email_input = page.locator("#email")
    email_input.wait_for(state="visible", timeout=8000)
    email_input.fill(email)

    # Fill password (id="password")
    pw_input = page.locator("#password")
    pw_input.wait_for(state="visible", timeout=8000)
    pw_input.fill(password)

    # Click the Log In button (id="btn-login")
    page.locator("#btn-login").click()

    # Wait for the SPA to navigate away from the login page
    try:
        page.wait_for_function(
            "() => !document.querySelector(\"input[type='password']\")",
            timeout=15000,
        )
    except PlaywrightTimeoutError:
        print("WARNING: Could not confirm login completed — continuing anyway.")

    page.wait_for_timeout(2000)

    # Navigate to the intended destination
    print(f"Navigating to {target_url} after login...")
    page.goto(target_url, wait_until="load")
    page.wait_for_timeout(2500)

    # Save the fresh session so we don't need to log in next time
    AUTH_STATE.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(AUTH_STATE))
    print("Session saved to auth/state.json")


# ---------------------------------------------------------------------------
# Sections / result.json
# ---------------------------------------------------------------------------

def load_sections(result_path: Path) -> dict[str, list[str]]:
    with open(result_path, encoding="utf-8") as f:
        data = json.load(f)
    sections = data.get("sections", {})
    if not isinstance(sections, dict):
        return {}
    return sections


# ---------------------------------------------------------------------------
# Equipment tab filler
# ---------------------------------------------------------------------------

def fill_subtab(page, tab_label: str, lines: list[str]) -> bool:
    """
    Click the named subtab, clear its editor, insert lines, save.
    Returns True on success, False if the tab or editor was not found.
    """
    # Click the subtab by its visible label
    try:
        tab = page.get_by_role("tab", name=tab_label, exact=True)
        tab.wait_for(state="visible", timeout=5000)
        tab.click()
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        print(f"  [MISS] Tab not found: '{tab_label}'")
        return False

    # Locate the active tab panel
    panel = page.locator(".ant-tabs-tabpane-active")
    if panel.count() == 0:
        print(f"  [MISS] Active panel not found after clicking: '{tab_label}'")
        return False

    # Locate the contenteditable editor inside the panel
    try:
        editor = panel.locator("[contenteditable='true']").first
        editor.wait_for(state="visible", timeout=5000)
        editor.click(force=True)
    except PlaywrightTimeoutError:
        print(f"  [MISS] No contenteditable editor in panel: '{tab_label}'")
        return False

    # Clear existing content
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(200)

    # Type each line
    non_empty = [str(l).strip() for l in lines if str(l).strip()]
    for i, line in enumerate(non_empty):
        page.keyboard.insert_text(line)
        if i < len(non_empty) - 1:
            page.keyboard.press("Enter")

    page.wait_for_timeout(300)

    # Save
    try:
        save_btn = panel.locator("[data-testid='texteditor-toolbar-save-button']").first
        save_btn.wait_for(state="visible", timeout=5000)
        save_btn.click()
        page.wait_for_timeout(800)
    except PlaywrightTimeoutError:
        print(f"  [MISS] Save button not found in panel: '{tab_label}'")
        return False

    print(f"  [OK]   {tab_label} — {len(non_empty)} lines saved")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    arg_parser = argparse.ArgumentParser(
        description="Fill YachtIQ Equipment tab subtabs from parser output"
    )
    arg_parser.add_argument("--id",    required=True, help="YachtIQ yacht ID (e.g. 447250)")
    arg_parser.add_argument("--input", default=None,  help="Path to result.json (default: output/result.json)")
    args = arg_parser.parse_args()

    result_path = Path(args.input) if args.input else OUTPUT_FILE
    if not result_path.exists():
        print(f"ERROR: result.json not found at {result_path}")
        print("  Run main.py first to generate it, or pass --input path/to/result.json")
        sys.exit(1)

    sections = load_sections(result_path)
    if not sections:
        print("No equipment sections found in result.json — nothing to fill.")
        sys.exit(0)

    # Only process subtabs that have content
    to_fill = {
        key: lines
        for key, lines in sections.items()
        if key in SUBTAB_LABELS and any(str(l).strip() for l in lines)
    }

    if not to_fill:
        print("None of the extracted sections match a known Equipment subtab.")
        sys.exit(0)

    print(f"Sections to fill: {', '.join(to_fill.keys())}")

    yacht_url = f"https://yachtiq.io/#/yacht/{args.id}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        # Use saved session if it exists; otherwise start a fresh context
        if AUTH_STATE.exists():
            context = browser.new_context(storage_state=str(AUTH_STATE))
        else:
            print("No saved session found — will log in from Login.txt")
            context = browser.new_context()

        page = context.new_page()

        print(f"Navigating to {yacht_url} ...")
        page.goto(yacht_url, wait_until="load")
        page.wait_for_timeout(2500)

        # If the session expired or never existed, we'll land on the login page
        if is_on_login_page(page):
            do_login(page, context, yacht_url)

        # Enter edit mode
        try:
            edit_btn = page.locator("button.ant-btn-icon-only").first
            edit_btn.wait_for(state="visible", timeout=8000)
            edit_btn.click()
            page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            print("ERROR: Edit button not found — did login succeed?")
            browser.close()
            sys.exit(1)

        # Click the top-level Equipment tab
        try:
            equipment_tab = page.get_by_role("tab", name="Equipment", exact=True)
            equipment_tab.wait_for(state="visible", timeout=8000)
            equipment_tab.click()
            page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            print("ERROR: Top-level Equipment tab not found.")
            browser.close()
            sys.exit(1)

        # Fill each subtab
        success_count = 0
        for key, lines in to_fill.items():
            label = SUBTAB_LABELS[key]
            print(f"\nFilling: {label}")
            if fill_subtab(page, label, lines):
                success_count += 1

        print(f"\nDone. {success_count}/{len(to_fill)} subtabs filled.")
        browser.close()


if __name__ == "__main__":
    main()
