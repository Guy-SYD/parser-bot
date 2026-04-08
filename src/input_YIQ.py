from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from difflib import SequenceMatcher
import sys as _sys
_sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from categorize_sections import categorize_sections as _categorize_sections

# ---------------------------
# INPUTS
# Use None or "" to skip
# ---------------------------

import argparse
import json
import re
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
PARSER_MAIN = BASE_DIR / "main.py"
OUTPUT_FILE = PROJECT_DIR / "output" / "result.json"
AUTH_STATE = PROJECT_DIR / "auth" / "state.json"
LOGIN_FILE  = PROJECT_DIR / "Login.txt"

# Equipment subtab: sections dict key → visible tab label on YachtIQ
# Order here defines the order tabs are filled.
EQUIPMENT_SUBTAB_LABELS = {
    "ACCOMMODATION":               "Accommodation",
    "GALLEY & LAUNDRY EQUIPMENT":  "Galley & Laundry Equipment",
    "COMMUNICATION EQUIPMENT":     "Communication Equipment",
    "NAVIGATION EQUIPMENT":        "Navigation Equipment",
    "ENTERTAINMENT EQUIPMENT":     "Entertainment Equipment",
    "TENDERS & TOYS":              "Tenders & Toys",
    "DECK EQUIPMENT":              "Deck Equipment",
    "RIGS & SAILS":                "Rigs & Sails",
    "SAFETY & SECURITY EQUIPMENT": "Safety & Security Equipment",
    "REFIT HISTORY":               "Refit History",
}

EQUIPMENT_SUBTAB_ORDER = [
    "ACCOMMODATION",
    "GALLEY & LAUNDRY EQUIPMENT",
    "COMMUNICATION EQUIPMENT",
    "NAVIGATION EQUIPMENT",
    "ENTERTAINMENT EQUIPMENT",
    "TENDERS & TOYS",
    "DECK EQUIPMENT",
    "RIGS & SAILS",
    "SAFETY & SECURITY EQUIPMENT",
    "REFIT HISTORY",
]

MAX_MAIN_ENGINES = 4
MAX_GENERATORS = 4

DROPDOWN_MISSES = []
FIELD_MISSES = []
DROPDOWN_NEAR_MATCHES = []


def identify_parser_source(traceback_text: str) -> str:
    matches = re.findall(
        r'File "([^"]+?\.py)", line (\d+), in ([^\n]+)',
        traceback_text
    )

    project_hits = []
    for file_path, line_no, func_name in matches:
        normalized = file_path.replace("/", "\\").lower()
        file_name = Path(file_path).name

        if "\\site-packages\\" in normalized:
            continue
        if "\\appdata\\local\\python\\" in normalized:
            continue
        if "\\lib\\" in normalized and "parser bot" not in normalized:
            continue
        if file_name.lower() == "input_yiq.py":
            continue

        project_hits.append((file_name, file_path, line_no, func_name))

    if not project_hits:
        return ""

    for file_name, file_path, line_no, func_name in reversed(project_hits):
        if file_name.lower().startswith("extract_"):
            return f"ERROR IN PARSER - likely extractor: {file_name} (line {line_no}, in {func_name})"

    file_name, file_path, line_no, func_name = project_hits[-1]
    return f"ERROR IN PARSER - likely source: {file_name} (line {line_no}, in {func_name})"


def load_credentials() -> tuple[str, str]:
    """Parse Login.txt and return (email, password)."""
    if not LOGIN_FILE.exists():
        raise FileNotFoundError(f"Login.txt not found: {LOGIN_FILE}")
    text = LOGIN_FILE.read_text(encoding="utf-8")
    email_match = re.search(r"(?i)email\s*:\s*(\S+)", text)
    pw_match    = re.search(r"(?i)(?:pw|password)\s*:\s*(\S+)", text)
    if not email_match or not pw_match:
        raise ValueError(f"Could not parse Email and PW from {LOGIN_FILE}")
    return email_match.group(1).strip(), pw_match.group(1).strip()


def is_on_login_page(page) -> bool:
    """Return True if the YachtIQ 'Welcome / Login' screen is showing."""
    return page.locator("#btn-login").count() > 0


def do_login(page, context, target_url: str):
    """Fill the login form, submit, navigate to target, then save the session."""
    print("Login page detected — signing in automatically...")
    email, password = load_credentials()

    page.locator("#email").wait_for(state="visible", timeout=8000)
    page.locator("#email").fill(email)
    page.locator("#password").fill(password)
    page.locator("#btn-login").click()

    # Wait until the password field disappears (login complete)
    try:
        page.wait_for_function(
            "() => !document.querySelector('#btn-login')",
            timeout=15000,
        )
    except PlaywrightTimeoutError:
        print("WARNING: Could not confirm login completed — continuing anyway.")

    page.wait_for_timeout(1500)
    page.goto(target_url, wait_until="load")
    page.wait_for_timeout(2500)

    # Save the fresh session for next time
    AUTH_STATE.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(AUTH_STATE))
    print("Session saved to auth/state.json")


def run_pdf_parser():
    if not PARSER_MAIN.exists():
        raise FileNotFoundError(f"Parser script not found: {PARSER_MAIN}")

    print("Running PDF parser to refresh output/result.json...")

    import time
    started_at = time.time()

    result = subprocess.run(
        [sys.executable, str(PARSER_MAIN)],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("\n===== PARSER STDOUT =====")
        print(result.stdout if result.stdout.strip() else "(no stdout)")

        print("\n===== PARSER STDERR =====")
        print(result.stderr if result.stderr.strip() else "(no stderr)")

        hint = identify_parser_source(result.stderr or "")
        if hint:
            print(f"\n{hint}")
        else:
            print("\nERROR IN PARSER")

        raise RuntimeError("main.py parser failed — not submitting to avoid sending bad data")

    # --- Check 1: output file must exist ---
    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(f"Parser completed, but output file not found: {OUTPUT_FILE}")

    # --- Check 2: output file must have been written during this run ---
    # If the file is older than when we started, the parser silently did nothing.
    file_mtime = OUTPUT_FILE.stat().st_mtime
    if file_mtime < started_at:
        raise RuntimeError(
            f"output/result.json was NOT updated by this parser run "
            f"(file is {int(started_at - file_mtime)}s older than the run start). "
            f"The parser may have exited early without writing output."
        )

    # --- Check 3: output file must contain a non-empty data block ---
    try:
        raw = OUTPUT_FILE.read_text(encoding="utf-8")
        parsed = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"output/result.json is not valid JSON after parsing: {exc}")

    data_block = parsed.get("data", {})
    filled_fields = {k: v for k, v in data_block.items() if v not in (None, "", [], {})}

    if not filled_fields:
        raise RuntimeError(
            "Parser ran without errors, but output/result.json contains no filled fields. "
            "The PDF may not have matched any known field patterns. "
            "Check that the correct PDF is in samples/ and that the field aliases cover its format."
        )


def load_schema_defaults():
    return {}


def extract_json_from_text(raw_text: str) -> dict:
    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return json.loads(match.group(1))

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw_text[start:end + 1])

    raise ValueError("Could not find valid JSON in the input file.")


def pick_input_file(input_path: str | None = None) -> Path:
    if input_path:
        path = Path(input_path)
        if not path.is_absolute():
            path = BASE_DIR / input_path
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        return path

    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(f"Default output file not found: {OUTPUT_FILE}")

    return OUTPUT_FILE


def derive_yacht_id(path: Path, explicit_id: str | None = None) -> str:
    if explicit_id:
        return explicit_id

    match = re.search(r"\d+", path.stem)
    if match:
        return match.group(0)

    raise ValueError(
        f"Could not derive yacht ID from filename '{path.name}'. "
        f"Run with --id 12345"
    )


def load_input_data(input_path: str | None = None, yacht_id: str | None = None):
    input_file = pick_input_file(input_path=input_path)
    raw_text = input_file.read_text(encoding="utf-8")
    incoming_json = extract_json_from_text(raw_text)

    incoming_data = incoming_json.get("data", incoming_json)

    data = load_schema_defaults()
    data.update(incoming_data)

    resolved_yacht_id = derive_yacht_id(input_file, explicit_id=yacht_id)
    yacht_url = f"https://yachtiq.io/#/yacht/{resolved_yacht_id}"

    return data, resolved_yacht_id, yacht_url, input_file


parser = argparse.ArgumentParser()
parser.add_argument("--input", help="Optional path to a specific input file")
parser.add_argument("--id", help="Yacht ID override")
parser.add_argument("--no-review", action="store_true", help="Skip the review prompt and close immediately")
parser.add_argument("--no-equipment", action="store_true", help="Skip the Equipment tab entirely")
args = parser.parse_args()

run_pdf_parser()

spec_data, YACHT_ID, YACHT_URL, INPUT_FILE = load_input_data(
    input_path=args.input,
    yacht_id=args.id,
)

for key, value in spec_data.items():
    globals()[key] = value

# Load equipment sections (may be empty if PDF had none)
_result_raw = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.exists() else "{}"
_result_json = json.loads(_result_raw)
EQUIPMENT_SECTIONS: dict = _result_json.get("sections", {})

# ---------------------------
# HELPERS
# ---------------------------

def has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def any_value(*values) -> bool:
    return any(has_value(v) for v in values)


def clear_and_fill_input(input_locator, value):
    if not has_value(value):
        return
    input_locator.click(force=True)
    input_locator.press("Control+A")
    input_locator.press("Backspace")
    input_locator.fill(str(value))


def fill_if_present(input_locator, value):
    if not has_value(value):
        return

    try:
        if input_locator.count() == 0:
            return
    except Exception:
        return

    clear_and_fill_input(input_locator, value)


def get_block_by_label(page_or_scope, label_text):
    return page_or_scope.locator("div.flex.flex-col").filter(
        has=page_or_scope.locator(f"label:text-is('{label_text}')")
    ).first


def get_block_by_label_contains(page_or_scope, label_text):
    ...

def xpath_literal(text):
    text = str(text)
    if "'" not in text:
        return f"'{text}'"
    if '"' not in text:
        return f'"{text}"'
    parts = text.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


def record_dropdown_miss(field_name, value, reason):
    DROPDOWN_MISSES.append({
        "field": field_name or "Unknown dropdown",
        "value": str(value),
        "reason": reason,
    })

def record_dropdown_near_match(field_name, wanted_value, matched_value, score):
    DROPDOWN_NEAR_MATCHES.append({
        "field": field_name or "Unknown dropdown",
        "wanted": str(wanted_value),
        "matched": str(matched_value),
        "score": score,
    })


def normalize_match_text(text):
    return " ".join(str(text).strip().lower().split())


def get_visible_ant_options_with_text(dropdown):
    options = dropdown.locator(
        "xpath=.//div[contains(@class,'ant-select-item-option') and not(contains(@class,'ant-select-item-option-disabled'))]"
    )

    results = []
    count = options.count()

    for i in range(count):
        option = options.nth(i)

        text = ""
        try:
            title = option.get_attribute("title")
            if has_value(title):
                text = str(title).strip()
            else:
                text = option.inner_text().strip()
        except Exception:
            try:
                text = option.inner_text().strip()
            except Exception:
                text = ""

        if has_value(text):
            results.append((option, text))

    return results


def choose_best_dropdown_option(option_pairs, wanted_value):
    """
    Returns: (option_locator, option_text, score, is_exact) or (None, None, 0, False)
    """
    if not option_pairs:
        return None, None, 0.0, False

    wanted_norm = normalize_match_text(wanted_value)

    # 1) exact normalized match first
    for option, text in option_pairs:
        if normalize_match_text(text) == wanted_norm:
            return option, text, 1.0, True

    # 2) otherwise best fuzzy match
    ranked = []
    wanted_tokens = set(wanted_norm.split())

    for option, text in option_pairs:
        text_norm = normalize_match_text(text)
        text_tokens = set(text_norm.split())

        ratio = SequenceMatcher(None, wanted_norm, text_norm).ratio()

        token_overlap = 0.0
        if wanted_tokens:
            token_overlap = len(wanted_tokens & text_tokens) / len(wanted_tokens)

        starts_bonus = 0.0
        if text_norm.startswith(wanted_norm) or wanted_norm.startswith(text_norm):
            starts_bonus = 0.08

        score = (ratio * 0.75) + (token_overlap * 0.25) + starts_bonus
        ranked.append((score, option, text))

    ranked.sort(key=lambda x: x[0], reverse=True)
    best_score, best_option, best_text = ranked[0]
    return best_option, best_text, best_score, False


def get_visible_ant_dropdown(page, timeout_ms=4000):
    dropdown = page.locator("div.ant-select-dropdown:not(.ant-select-dropdown-hidden)").last
    try:
        dropdown.wait_for(state="visible", timeout=timeout_ms)
        return dropdown
    except PlaywrightTimeoutError:
        return None


def get_visible_ant_option(dropdown, value):
    value_xpath = xpath_literal(str(value).strip())
    return dropdown.locator(
        f"xpath=.//div[contains(@class,'ant-select-item-option')]"
        f"[@title={value_xpath} or @label={value_xpath} or @name={value_xpath} "
        f"or normalize-space(.)={value_xpath} or .//*[normalize-space(.)={value_xpath}]]"
    )


def select_dropdown_by_typing(
    dropdown_locator,
    value,
    page,
    field_name=None,
    wait_ms=500,
    allow_best_visible_match=False,
    min_best_match_score=0.72,
):
    if not has_value(value):
        return False

    value = str(value).strip()

    try:
        dropdown_locator.click(force=True)
        page.wait_for_timeout(200)

        search_input = dropdown_locator.locator("input.ant-select-selection-search-input").first
        try:
            search_input.click(force=True)
        except Exception:
            pass

        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.insert_text(value)

        page.wait_for_timeout(wait_ms)

        visible_dropdown = get_visible_ant_dropdown(page, timeout_ms=2000)
        if visible_dropdown is None:
            record_dropdown_miss(field_name, value, "No dropdown results appeared")
            page.keyboard.press("Escape")
            return False

        option_pairs = get_visible_ant_options_with_text(visible_dropdown)

        if not option_pairs:
            # Typed value filtered everything out — clear the search and show all options
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.wait_for_timeout(wait_ms)
            visible_dropdown = get_visible_ant_dropdown(page, timeout_ms=2000)
            if visible_dropdown:
                option_pairs = get_visible_ant_options_with_text(visible_dropdown)

        if not option_pairs:
            record_dropdown_miss(field_name, value, "No selectable options in dropdown")
            page.keyboard.press("Escape")
            return False

        # If exactly one option remains, always select it — the search narrowed it unambiguously
        if len(option_pairs) == 1:
            option_pairs[0][0].click(timeout=2000)
            page.wait_for_timeout(150)
            return True

        best_option, best_text, best_score, is_exact = choose_best_dropdown_option(option_pairs, value)

        if is_exact:
            best_option.click(timeout=2000)
            page.wait_for_timeout(150)
            return True

        if allow_best_visible_match and best_option is not None and best_score >= min_best_match_score:
            best_option.click(timeout=2000)
            page.wait_for_timeout(150)
            record_dropdown_near_match(field_name, value, best_text, round(best_score, 3))
            return True

        record_dropdown_miss(field_name, value, "No exact matching option in dropdown")
        page.keyboard.press("Escape")
        return False

    except Exception as e:
        record_dropdown_miss(field_name, value, f"Selection failed: {e}")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def select_autocomplete_by_name(
    dropdown_locator,
    value,
    page,
    field_name=None,
    wait_ms=400,
    allow_best_visible_match=False,
    min_best_match_score=0.72,
):
    if not has_value(value):
        return False

    return select_dropdown_by_typing(
        dropdown_locator,
        value,
        page,
        field_name=field_name,
        wait_ms=wait_ms,
        allow_best_visible_match=allow_best_visible_match,
        min_best_match_score=min_best_match_score,
    )


def select_dropdown_arrow_once(dropdown_locator, page):
    dropdown_locator.click(force=True)
    page.wait_for_timeout(100)
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(100)
    page.keyboard.press("Enter")
    page.wait_for_timeout(100)

def fill_measure_block(block, page, ft_value=None, inch_value=None, unit_value=None, metric_value=None):
    if not any_value(ft_value, inch_value, unit_value, metric_value):
        return

    if has_value(ft_value):
        ft_wrapper = block.locator("span.ant-input-affix-wrapper").filter(
            has=block.locator("span:text-is('ft')")
        ).first
        fill_if_present(ft_wrapper.locator("input").first, ft_value)

    if has_value(inch_value):
        in_wrapper = block.locator("span.ant-input-affix-wrapper").filter(
            has=block.locator("span:text-is('in')")
        ).first
        fill_if_present(in_wrapper.locator("input").first, inch_value)

    if has_value(unit_value):
        unit_dropdown = block.locator("div.ant-select.ant-select-compact-last-item").first
        try:
            select_dropdown_by_typing(unit_dropdown, unit_value, page, exact_title_click=True)
        except Exception:
            select_dropdown_arrow_once(unit_dropdown, page)

    if has_value(metric_value):
        m_wrapper = block.locator("span.ant-input-affix-wrapper").filter(
            has=block.locator("span:text-is('m')")
        ).first
        fill_if_present(m_wrapper.locator("input").first, metric_value)


def fill_compact_value_pair(block, page, first_value=None, second_value=None, field_name="Unknown field"):
    if not any_value(first_value, second_value):
        return

    if block is None:
        print(f"[MISS] {field_name}: block was None")
        return

    try:
        if block.count() == 0:
            print(f"[MISS] {field_name}: block not found")
            return
    except Exception:
        pass

    wrapper = block.locator("div.ant-space-compact").first

    try:
        if wrapper.count() == 0:
            print(f"[MISS] {field_name}: compact wrapper not found")
            return
    except Exception:
        pass

    input_box = wrapper.locator("> input").first
    unit_dropdown = wrapper.locator("div.ant-select.ant-select-compact-last-item").first

    if has_value(first_value):
        fill_if_present(input_box, first_value)

    if has_value(second_value):
        select_dropdown_arrow_once(unit_dropdown, page)
        fill_if_present(input_box, second_value)


def fill_built_refit(block, built_value=None, refit_value=None):
    if not any_value(built_value, refit_value):
        return

    inputs = block.locator("input.ant-input-number-input")
    if has_value(built_value):
        fill_if_present(inputs.nth(0), built_value)
    if has_value(refit_value):
        fill_if_present(inputs.nth(1), refit_value)


def _is_equipment_header(line: str) -> bool:
    """
    Return True only for bare category name lines — nothing after the colon.

    Examples that become bold:
      "GPS:"            "VHF:"          "Satcom:"
      "Wind / Speed Log:"               "Magnetic compass:"

    Examples that stay as plain bullets (content after colon, or no colon):
      "Radar: Furuno FR BB 2117 X Band"
      "Chart Plotter: Furuno/MAXSEA"
      "(2) Furuno GP-150"
      "SUR LA MER accommodates up to..."
    """
    stripped = line.strip()
    if not stripped:
        return False
    # Must end with colon and have nothing after it, label ≤ 40 chars
    m = re.match(r'^([^:]{1,40}):\s*$', stripped)
    if not m:
        return False
    label = m.group(1).strip()
    # Exclude if label starts with digit or quantity marker
    if re.match(r'^\(?\d', label):
        return False
    return True


def _split_header_item(line: str):
    """
    For a bare 'Label:' line return (label, None).
    All other lines return (None, line).
    """
    stripped = line.strip()
    m = re.match(r'^([^:]{1,40}):\s*$', stripped)
    if m:
        label = m.group(1).strip()
        if not re.match(r'^\(?\d', label):
            return label, None
    return None, stripped


def _join_wrapped_lines(lines: list[str]) -> list[str]:
    """
    Join PDF word-wrap continuations into single logical lines.
    A continuation starts lowercase and the previous line doesn't end in .!?:
    """
    joined = []
    for line in lines:
        if (
            joined
            and joined[-1]
            and joined[-1][-1] not in '.!?:'
            and re.match(r'^[a-z]', line)
            and not re.match(r'^\(?\d', line)
        ):
            sep = '' if joined[-1].endswith('-') else ' '
            joined[-1] = joined[-1].rstrip('-') + sep + line
        else:
            joined.append(line)
    return joined


def write_equipment_content(panel, page, structured: list[tuple[str, list[str]]]):
    """
    Write categorised equipment content into a Lexical editor via HTML clipboard paste.

    Builds an HTML string where category headers are <strong> and content
    lines are plain paragraphs prefixed with '• '.  Writes both HTML and
    plain-text representations to the system clipboard via the ClipboardItem
    API, then pastes with Ctrl+V so Lexical receives rich formatting and
    renders headers in bold.

    structured: [(category_name, [content_lines]), ...]
      - category_name non-empty → <p><strong>name</strong></p>
      - content_lines           → <p>• line</p>
    """
    import html as _html

    html_parts: list[str] = []
    plain_parts: list[str] = []

    for cat_name, lines in structured:
        if cat_name:
            print(f"    [H] {cat_name}")
            html_parts.append(f"<p><strong>{_html.escape(cat_name)}</strong></p>")
            plain_parts.append(cat_name)
        for line in _join_wrapped_lines(lines):
            print(f"    [ ] {line[:90]}")
            html_parts.append(f"<p>• {_html.escape(line)}</p>")
            plain_parts.append("• " + line)

    html_content  = "\n".join(html_parts)
    plain_content = "\n".join(plain_parts)

    # Write HTML + plain text to clipboard via ClipboardItem API
    page.evaluate("""
        async ([html, plain]) => {
            await navigator.clipboard.write([
                new ClipboardItem({
                    'text/html':  new Blob([html],  {type: 'text/html'}),
                    'text/plain': new Blob([plain], {type: 'text/plain'}),
                })
            ]);
        }
    """, [html_content, plain_content])
    page.wait_for_timeout(200)

    editor = panel.locator("[contenteditable='true']").first
    editor.click(force=True)
    page.wait_for_timeout(150)

    # Clear editor content via JS — avoids Ctrl+A selecting the whole page
    editor.evaluate("el => { el.innerHTML = ''; el.focus(); }")
    page.wait_for_timeout(150)

    # Single paste event — Lexical receives the HTML and renders bold headers
    page.keyboard.press("Control+V")
    page.wait_for_timeout(800)

    panel.locator("[data-testid='texteditor-toolbar-save-button']").first.click()
    page.wait_for_timeout(800)


def fill_richtext_bullets(section, bullets, page):
    if not has_value(bullets):
        return

    editor = section.locator("[data-testid*='texteditor-contenteditable']").first
    editor.click(force=True)

    section.locator("[data-testid='toolbar-list-ul']").first.click()

    # clear existing content
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")

    for i, item in enumerate(bullets):
        if not has_value(item):
            continue
        page.keyboard.insert_text(str(item))
        if i < len(bullets) - 1:
            page.keyboard.press("Enter")

    section.locator("[data-testid='texteditor-toolbar-save-button']").first.click()


def get_repeater_rows(section, row_heading_prefix):
    prefix_xpath = xpath_literal(row_heading_prefix)
    return section.locator(
        f"xpath=.//h3[contains(normalize-space(.), {prefix_xpath})]"
        f"/ancestor::div[contains(@class,'border-l-4')][1]"
    )


def ensure_row_count(section, page, target_count, row_heading_prefix, max_count):
    target_count = min(target_count, max_count)
    rows = get_repeater_rows(section, row_heading_prefix)

    while rows.count() < target_count:
        add_button = section.get_by_role("button", name="+ Add")
        if add_button.count() == 0:
            print(f"[MISS] {row_heading_prefix}: + Add button not found")
            break

        add_button.click()
        page.wait_for_timeout(200)
        rows = get_repeater_rows(section, row_heading_prefix)


def get_row_field_card(row_block, label_text):
    label_xpath = xpath_literal(label_text)
    field = row_block.locator(
        f"xpath=.//label[normalize-space(.)={label_xpath}]"
        f"/ancestor::div[contains(@class,'flex') and contains(@class,'flex-col')][1]"
    ).first

    try:
        if field.count() == 0:
            return None
    except Exception:
        return None

    return field

def get_selected_ant_select_text(dropdown_locator):
    try:
        item = dropdown_locator.locator(".ant-select-selection-item").first
        if item.count() == 0:
            return ""

        title = item.get_attribute("title")
        text = (title or item.inner_text() or "").strip()
        return text
    except Exception:
        return ""

def fill_engine_like_block(
    block,
    page,
    data,
    row_name,
    toggle_output_before_fill=False,
    output_unit=None,
    preserve_existing_output_unit=False,
):
    if has_value(data.get("make")):
        make_block = get_row_field_card(block, "Engine make")
        if make_block is None:
            print(f"[MISS] {row_name}: field not found -> Engine make")
        else:
            select_dropdown_by_typing(
                make_block.locator("div.ant-select").first,
                data["make"],
                page,
                field_name=f"{row_name} - Engine make"
            )

    if has_value(data.get("model")):
        model_block = get_row_field_card(block, "Engine model")
        if model_block is None:
            print(f"[MISS] {row_name}: field not found -> Engine model")
        else:
            fill_if_present(model_block.locator("input").first, data["model"])

    if has_value(data.get("type")):
        type_block = get_row_field_card(block, "Engine type")
        if type_block is None:
            print(f"[MISS] {row_name}: field not found -> Engine type")
        else:
            select_dropdown_by_typing(
                type_block.locator("div.ant-select").first,
                data["type"],
                page,
                field_name=f"{row_name} - Engine type"
            )

    if has_value(data.get("fuel_type")):
        fuel_block = get_row_field_card(block, "Fuel type")
        if fuel_block is None:
            print(f"[MISS] {row_name}: field not found -> Fuel type")
        else:
            select_dropdown_by_typing(
                fuel_block.locator("div.ant-select").first,
                data["fuel_type"],
                page,
                field_name=f"{row_name} - Fuel type"
            )

    if has_value(data.get("output")):
        output_block = get_row_field_card(block, "Engine output")
        if output_block is None:
            print(f"[MISS] {row_name}: field not found -> Engine output")
        else:
            output_input = output_block.locator(
                "div.ant-space-compact > input, div.ant-space-compact input"
            ).first

            output_unit_dropdown = output_block.locator(
                "div.ant-select.ant-select-compact-last-item"
            ).first

            if has_value(output_unit):
                current_unit = get_selected_ant_select_text(output_unit_dropdown)

                if not (
                    preserve_existing_output_unit
                    and has_value(current_unit)
                ):
                    if not (has_value(current_unit) and current_unit.lower() == str(output_unit).strip().lower()):
                        select_dropdown_by_typing(
                            output_unit_dropdown,
                            output_unit,
                            page,
                            field_name=f"{row_name} - Output unit",
                            wait_ms=350
                        )

            elif toggle_output_before_fill:
                select_dropdown_arrow_once(output_unit_dropdown, page)

            fill_if_present(output_input, data["output"])

    if has_value(data.get("hours")):
        hours_block = get_row_field_card(block, "Engine hours")
        if hours_block is None:
            print(f"[MISS] {row_name}: field not found -> Engine hours")
        else:
            fill_if_present(hours_block.locator("input.ant-input-number-input, input").first, data["hours"])

    if has_value(data.get("location")):
        location_block = get_row_field_card(block, "Location")
        if location_block is None:
            print(f"[MISS] {row_name}: field not found -> Location")
        else:
            select_dropdown_by_typing(
                location_block.locator("div.ant-select").first,
                data["location"],
                page,
                field_name=f"{row_name} - Location"
            )


def get_card_by_label_text(page_or_scope, label_fragment):
    label_fragment = str(label_fragment).strip().lower()
    label_xpath = xpath_literal(label_fragment)

    card = page_or_scope.locator(
        f"xpath=.//div[contains(@class,'flex') and contains(@class,'flex-col')]"
        f"[.//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {label_xpath})]]"
    ).first

    try:
        if card.count() == 0:
            return None
    except Exception:
        return None

    return card

def get_card_by_any_label_text(page_or_scope, label_fragments):
    for label_fragment in label_fragments:
        card = get_card_by_label_text(page_or_scope, label_fragment)
        if card is not None:
            return card
    return None

# ---------------------------
# DATA GROUPING
# ---------------------------

MAIN_ENGINES = [
    {
        "title": "Main Engine #1",
        "make": ENGINE_1_MAKE,
        "model": ENGINE_1_MODEL,
        "type": ENGINE_1_TYPE,
        "fuel_type": ENGINE_1_FUEL_TYPE,
        "output": ENGINE_1_OUTPUT_HP,
        "hours": ENGINE_1_HOURS,
        "location": ENGINE_1_LOCATION,
    },
    {
        "title": "Main Engine #2",
        "make": ENGINE_2_MAKE,
        "model": ENGINE_2_MODEL,
        "type": ENGINE_2_TYPE,
        "fuel_type": ENGINE_2_FUEL_TYPE,
        "output": ENGINE_2_OUTPUT_HP,
        "hours": ENGINE_2_HOURS,
        "location": ENGINE_2_LOCATION,
    },
    {
        "title": "Main Engine #3",
        "make": ENGINE_3_MAKE,
        "model": ENGINE_3_MODEL,
        "type": ENGINE_3_TYPE,
        "fuel_type": ENGINE_3_FUEL_TYPE,
        "output": ENGINE_3_OUTPUT_HP,
        "hours": ENGINE_3_HOURS,
        "location": ENGINE_3_LOCATION,
    },
    {
        "title": "Main Engine #4",
        "make": ENGINE_4_MAKE,
        "model": ENGINE_4_MODEL,
        "type": ENGINE_4_TYPE,
        "fuel_type": ENGINE_4_FUEL_TYPE,
        "output": ENGINE_4_OUTPUT_HP,
        "hours": ENGINE_4_HOURS,
        "location": ENGINE_4_LOCATION,
    },

]

GENERATORS = [
    {
        "title": "Generator #1",
        "make": GENERATOR_1_MAKE,
        "model": GENERATOR_1_MODEL,
        "type": GENERATOR_1_TYPE,
        "fuel_type": GENERATOR_1_FUEL_TYPE,
        "output": GENERATOR_1_OUTPUT,
        "hours": GENERATOR_1_HOURS,
        "location": GENERATOR_1_LOCATION,
    },
    {
        "title": "Generator #2",
        "make": GENERATOR_2_MAKE,
        "model": GENERATOR_2_MODEL,
        "type": GENERATOR_2_TYPE,
        "fuel_type": GENERATOR_2_FUEL_TYPE,
        "output": GENERATOR_2_OUTPUT,
        "hours": GENERATOR_2_HOURS,
        "location": GENERATOR_2_LOCATION,
    },
    {
        "title": "Generator #3",
        "make": GENERATOR_3_MAKE,
        "model": GENERATOR_3_MODEL,
        "type": GENERATOR_3_TYPE,
        "fuel_type": GENERATOR_3_FUEL_TYPE,
        "output": GENERATOR_3_OUTPUT,
        "hours": GENERATOR_3_HOURS,
        "location": GENERATOR_3_LOCATION,
    },
    {
        "title": "Generator #4",
        "make": GENERATOR_4_MAKE,
        "model": GENERATOR_4_MODEL,
        "type": GENERATOR_4_TYPE,
        "fuel_type": GENERATOR_4_FUEL_TYPE,
        "output": GENERATOR_4_OUTPUT,
        "hours": GENERATOR_4_HOURS,
        "location": GENERATOR_4_LOCATION,
    },
]


# ---------------------------
# MAIN
# ---------------------------

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    if AUTH_STATE.exists():
        context = browser.new_context(
            storage_state=str(AUTH_STATE),
            permissions=["clipboard-read", "clipboard-write"],
        )
    else:
        print("No saved session found — will log in from Login.txt")
        context = browser.new_context(
            permissions=["clipboard-read", "clipboard-write"],
        )

    page = context.new_page()

    page.goto(YACHT_URL, wait_until="load")
    page.wait_for_timeout(2500)

    if is_on_login_page(page):
        do_login(page, context, YACHT_URL)

    # Edit
    page.locator("button.ant-btn-icon-only").first.click()
    page.wait_for_timeout(1000)

    # ---------------------------
    # GENERAL / SUMMARY
    # ---------------------------

    # LOA
    if any_value(LOA_FT, LOA_IN, LOA_M):
        loa_section = page.locator(
            "xpath=//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'loa')]/following-sibling::div[1]"
        ).first

        if has_value(LOA_FT):
            loa_ft_input = loa_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='ft']]//input"
            ).first
            fill_if_present(loa_ft_input, LOA_FT)

        if has_value(LOA_IN):
            loa_in_input = loa_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='in']]//input"
            ).first
            fill_if_present(loa_in_input, LOA_IN)

        if has_value(LOA_M):
            loa_unit_dropdown = loa_section.locator(
                "xpath=.//div[contains(@class,'ant-select') and contains(@class,'ant-select-compact-last-item')]"
            ).first
            select_dropdown_arrow_once(loa_unit_dropdown, page)

            page.wait_for_timeout(250)

            loa_section = page.locator(
                "xpath=//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'loa')]/following-sibling::div[1]"
            ).first

            loa_m_input = loa_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='m']]//input"
            ).first
            fill_if_present(loa_m_input, LOA_M)

    # Built / Refit
    built_refit_block = page.locator("div.flex.flex-col").filter(
        has=page.locator("label", has_text="Built / Refit")
    ).first

    if has_value(YEAR):
        built_input = built_refit_block.locator("input.ant-input-number-input").nth(0)
        fill_if_present(built_input, YEAR)

    if has_value(REFIT):
        refit_input = built_refit_block.locator("input.ant-input-number-input").nth(1)
        fill_if_present(refit_input, REFIT)

    # Builder
    if has_value(BUILDER):
        builder_block = get_block_by_label(page, "builder")
        builder_select = builder_block.locator("div.ant-select.ant-select-auto-complete").first
        select_autocomplete_by_name(
            builder_select,
            BUILDER,
            page,
            field_name="Builder",
            allow_best_visible_match=True,
            min_best_match_score=0.78
        )

    # Gross tonnage
    if has_value(GT):
        gt_block = get_block_by_label(page, "Gross tonnage")
        gt_input = gt_block.locator("div.ant-input-number-wrapper.ant-input-number-group").first.locator(
            "input.ant-input-number-input"
        ).first
        fill_if_present(gt_input, GT)

    # Staterooms / Guests / Crew
    if has_value(STATEROOMS):
        fill_if_present(
            page.locator("//label[normalize-space()='Staterooms']/following-sibling::div//input[contains(@class,'ant-input-number-input')]").first,
            STATEROOMS
        )

    if has_value(GUESTS):
        fill_if_present(
            page.locator("//label[normalize-space()='Guests']/following-sibling::div//input[contains(@class,'ant-input-number-input')]").first,
            GUESTS
        )

    if has_value(CREW):
        fill_if_present(
            page.locator("//label[normalize-space()='Crew']/following-sibling::div//input[contains(@class,'ant-input-number-input')]").first,
            CREW
        )

    # ---------------------------
    # DIMENSIONS TAB
    # ---------------------------

    page.get_by_role("tab", name="Dimensions").click()
    page.wait_for_timeout(200)

    # Beam
    if any_value(BEAM_FT, BEAM_IN, BEAM_M):
        beam_section = page.locator(
            "xpath=//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'beam')]/following-sibling::div[1]"
        ).first

        if has_value(BEAM_FT):
            beam_ft_input = beam_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='ft']]//input"
            ).first
            fill_if_present(beam_ft_input, BEAM_FT)

        if has_value(BEAM_IN):
            beam_in_input = beam_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='in']]//input"
            ).first
            fill_if_present(beam_in_input, BEAM_IN)

        if has_value(BEAM_M):
            beam_unit_dropdown = beam_section.locator(
                "xpath=.//div[contains(@class,'ant-select') and contains(@class,'ant-select-compact-last-item')]"
            ).first
            select_dropdown_arrow_once(beam_unit_dropdown, page)

            page.wait_for_timeout(250)

            beam_section = page.locator(
                "xpath=//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'beam')]/following-sibling::div[1]"
            ).first

            beam_m_input = beam_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='m']]//input"
            ).first
            fill_if_present(beam_m_input, BEAM_M)



    # Max. Draft
    if any_value(MAX_DRAFT_FT, MAX_DRAFT_IN, MAX_DRAFT_M):
        max_draft_section = page.locator(
            "xpath=//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'max. draft')]/following-sibling::div[1]"
        ).first

        if has_value(MAX_DRAFT_FT):
            max_draft_ft_input = max_draft_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='ft']]//input"
            ).first
            fill_if_present(max_draft_ft_input, MAX_DRAFT_FT)

        if has_value(MAX_DRAFT_IN):
            max_draft_in_input = max_draft_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='in']]//input"
            ).first
            fill_if_present(max_draft_in_input, MAX_DRAFT_IN)

        if has_value(MAX_DRAFT_M):
            max_draft_unit_dropdown = max_draft_section.locator(
                "xpath=.//div[contains(@class,'ant-select') and contains(@class,'ant-select-compact-last-item')]"
            ).first
            select_dropdown_arrow_once(max_draft_unit_dropdown, page)

            page.wait_for_timeout(250)

            max_draft_section = page.locator(
                "xpath=//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'max. draft')]/following-sibling::div[1]"
            ).first

            max_draft_m_input = max_draft_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='m']]//input"
            ).first
            fill_if_present(max_draft_m_input, MAX_DRAFT_M)

    # Min. Draft
    if any_value(MIN_DRAFT_FT, MIN_DRAFT_IN, MIN_DRAFT_M):
        min_draft_section = page.locator(
            "xpath=//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'min. draft')]/following-sibling::div[1]"
        ).first

        if has_value(MIN_DRAFT_FT):
            min_draft_ft_input = min_draft_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='ft']]//input"
            ).first
            fill_if_present(min_draft_ft_input, MIN_DRAFT_FT)

        if has_value(MIN_DRAFT_IN):
            min_draft_in_input = min_draft_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='in']]//input"
            ).first
            fill_if_present(min_draft_in_input, MIN_DRAFT_IN)

        if has_value(MIN_DRAFT_M):
            min_draft_unit_dropdown = min_draft_section.locator(
                "xpath=.//div[contains(@class,'ant-select') and contains(@class,'ant-select-compact-last-item')]"
            ).first
            select_dropdown_arrow_once(min_draft_unit_dropdown, page)

            page.wait_for_timeout(250)

            min_draft_section = page.locator(
                "xpath=//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'min. draft')]/following-sibling::div[1]"
            ).first

            min_draft_m_input = min_draft_section.locator(
                "xpath=.//span[contains(@class,'ant-input-affix-wrapper')][.//span[normalize-space()='m']]//input"
            ).first
            fill_if_present(min_draft_m_input, MIN_DRAFT_M)



    if has_value(YACHT_TYPE):
        yacht_type_block = get_block_by_label(page, "Yacht type")
        select_dropdown_by_typing(
            yacht_type_block.locator("div.ant-select").first,
            YACHT_TYPE,
            page,
            field_name="Yacht type"
        )

    if has_value(MODEL):
        model_input = page.locator(
            "//label[normalize-space()='Model']/preceding-sibling::div//input[contains(@class,'ant-input')]"
        ).first
        fill_if_present(model_input, MODEL)

    if has_value(HULL_NUMBER):
        hull_number_input = page.locator(
            "//label[normalize-space()='Hull number']/preceding-sibling::div//input[contains(@class,'ant-input')]"
        ).first
        fill_if_present(hull_number_input, HULL_NUMBER)

    if has_value(HULL_MATERIAL):
        hull_material_block = get_block_by_label(page, "Hull Material")
        select_dropdown_by_typing(
            hull_material_block.locator("div.ant-select").first,
            HULL_MATERIAL,
            page,
            field_name="Hull Material",
            allow_best_visible_match=True,
            min_best_match_score=0.4,
        )

    if has_value(HULL_CONFIGURATION):
        hull_config_block = get_block_by_label(page, "Hull configuration")
        select_dropdown_by_typing(
            hull_config_block.locator("div.ant-select").first,
            HULL_CONFIGURATION,
            page,
            field_name="Hull configuration"
        )

    if has_value(SUPERSTRUCTURE_MATERIAL):
        superstructure_block = get_block_by_label(page, "Superstructure Material")
        # GRP and Fibreglass are the same material — normalise so the dropdown search finds it
        superstructure_search = SUPERSTRUCTURE_MATERIAL
        if re.fullmatch(r"grp", superstructure_search.strip(), flags=re.IGNORECASE):
            superstructure_search = "Fiberglass"
        select_dropdown_by_typing(
            superstructure_block.locator("div.ant-select").first,
            superstructure_search,
            page,
            field_name="Superstructure Material",
            allow_best_visible_match=True,
            min_best_match_score=0.4,
        )

    if has_value(EXTERIOR_DESIGNER):
        exterior_block = get_block_by_label(page, "Exterior designer")
        select_autocomplete_by_name(
            exterior_block.locator("div.ant-select.ant-select-auto-complete").first,
            EXTERIOR_DESIGNER,
            page,
            field_name="Exterior designer",
            allow_best_visible_match=True,
            min_best_match_score=0.78
        )

    if has_value(INTERIOR_DESIGNER):
        interior_block = get_block_by_label(page, "Interior designer")
        select_autocomplete_by_name(
            interior_block.locator("div.ant-select.ant-select-auto-complete").first,
            INTERIOR_DESIGNER,
            page,
            field_name="Interior designer",
            allow_best_visible_match=True,
            min_best_match_score=0.78
        )


    if has_value(NAVAL_ARCHITECT):
        naval_block = get_block_by_label(page, "Naval architect")
        select_autocomplete_by_name(
            naval_block.locator("div.ant-select.ant-select-auto-complete").first,
            NAVAL_ARCHITECT,
            page,
            field_name="Naval architect",
            allow_best_visible_match=True,
            min_best_match_score=0.78
        )

    if has_value(MAX_SPEED):
        max_speed_block = get_card_by_label_text(page, "max. speed")
        if max_speed_block is not None:
            fill_if_present(
                max_speed_block.locator("input.ant-input-number-input").first,
                MAX_SPEED
            )

    if has_value(CRUISE_SPEED):
        cruise_speed_block = get_card_by_label_text(page, "cruise speed")
        if cruise_speed_block is not None:
            fill_if_present(
                cruise_speed_block.locator("input.ant-input-number-input").first,
                CRUISE_SPEED
            )

    if has_value(ECONOMICAL_SPEED):
        economical_speed_block = get_card_by_label_text(page, "economical speed")
        if economical_speed_block is not None:
            fill_if_present(
                economical_speed_block.locator("input.ant-input-number-input").first,
                ECONOMICAL_SPEED
            )

    if has_value(MAX_RANGE):
        max_range_block = get_card_by_label_text(page, "max. range")
        if max_range_block is not None:
            fill_if_present(
                max_range_block.locator("input.ant-input").first,
                MAX_RANGE
            )

    if has_value(CRUISE_RANGE):
        cruise_range_block = get_card_by_label_text(page, "cruise range")
        if cruise_range_block is not None:
            fill_if_present(
                cruise_range_block.locator("input.ant-input-number-input").first,
                CRUISE_RANGE
            )

    if has_value(ECONOMICAL_RANGE):
        economical_range_block = get_card_by_label_text(page, "economical range")
        if economical_range_block is not None:
            fill_if_present(
                economical_range_block.locator("input.ant-input-number-input").first,
                ECONOMICAL_RANGE
            )



    # Paired compact fields

    compact_pairs = [
        ("Cruising Consumption", CRUISING_CONSUMPTION_L, CRUISING_CONSUMPTION_GAL),
        ("Economical Consumption", ECONOMICAL_CONSUMPTION_L, ECONOMICAL_CONSUMPTION_GAL),
        ("Fuel", FUEL_L, FUEL_GAL),
        ("Fresh Water", FRESH_WATER_L, FRESH_WATER_GAL),
        ("Lube Oil", LUBE_OIL_L, LUBE_OIL_GAL),
    ]

    for label, first_val, second_val in compact_pairs:
        if any_value(first_val, second_val):
            block = get_card_by_label_text(page, label)
            fill_compact_value_pair(block, page, first_val, second_val, field_name=label)

    if any_value(BLACK_WATER_HOLDING_TANK_L, BLACK_WATER_HOLDING_TANK_GAL):
        black_water_block = get_card_by_label_text(page, "black water holding tank")
        fill_compact_value_pair(
            black_water_block,
            page,
            BLACK_WATER_HOLDING_TANK_L,
            BLACK_WATER_HOLDING_TANK_GAL,
            field_name="Black Water Holding Tank"
        )

    if any_value(GREY_WATER_HOLDING_TANK_L, GREY_WATER_HOLDING_TANK_GAL):
        grey_water_block = get_card_by_label_text(page, "grey water holding tank")
        fill_compact_value_pair(
            grey_water_block,
            page,
            GREY_WATER_HOLDING_TANK_L,
            GREY_WATER_HOLDING_TANK_GAL,
            field_name="Grey Water Holding Tank"
        )

    if any_value(WASTE_OIL_L, WASTE_OIL_GAL):
        waste_oil_block = get_card_by_label_text(page, "waste oil")
        fill_compact_value_pair(
            waste_oil_block,
            page,
            WASTE_OIL_L,
            WASTE_OIL_GAL,
            field_name="Waste Oil"
        )

    if has_value(IACS_SOCIETY):
        iacs_block = get_card_by_label_text(page, "iacs society")

        if iacs_block is None:
            print("[MISS] IACS society: card not found")
        else:
            iacs_dropdown = iacs_block.locator("div.ant-select").first

            try:
                if iacs_dropdown.count() == 0:
                    print("[MISS] IACS society: dropdown not found")
                else:
                    select_dropdown_by_typing(
                        iacs_dropdown,
                        IACS_SOCIETY,
                        page,
                        field_name="IACS society",
                        allow_best_visible_match=True,
                        min_best_match_score=0.68
                    )
            except Exception as e:
                print(f"[MISS] IACS society: {e}")

    if has_value(MMSI):
        mmsi_block = get_card_by_label_text(page, "mmsi")
        if mmsi_block is None:
            print("[MISS] MMSI: card not found")
        else:
            mmsi_input = mmsi_block.locator("input").first
            fill_if_present(mmsi_input, MMSI)

    if has_value(IMO):
        imo_block = get_card_by_label_text(page, "imo")
        if imo_block is None:
            print("[MISS] IMO: card not found")
        else:
            imo_input = imo_block.locator("input").first
            fill_if_present(imo_input, IMO)

    if has_value(FLAG):
        flag_block = get_card_by_label_text(page, "flag")
        if flag_block is None:
            print("[MISS] Flag: card not found")
        else:
            flag_input = flag_block.locator("input").first
            fill_if_present(flag_input, FLAG)

    if has_value(REGISTRY_PORT):
        registry_block = get_card_by_label_text(page, "registry port")
        if registry_block is None:
            print("[MISS] Registry Port: card not found")
        else:
            registry_input = registry_block.locator("input").first
            fill_if_present(registry_input, REGISTRY_PORT)

    if has_value(COMMERCIAL_COMPLIANCE):
        compliance_block = get_card_by_label_text(page, "commercial compliance")

        if compliance_block is None:
            print("[MISS] Commercial Compliance: card not found")
        else:
            compliance_dropdown = compliance_block.locator("div.ant-select").first

            try:
                if compliance_dropdown.count() == 0:
                    print("[MISS] Commercial Compliance: dropdown not found")
                else:
                    select_dropdown_by_typing(
                        compliance_dropdown,
                        COMMERCIAL_COMPLIANCE,
                        page,
                        field_name="Commercial Compliance"
                    )
            except Exception as e:
                print(f"[MISS] Commercial Compliance: {e}")



    # ---------------------------
    # MECHANICAL TAB
    # ---------------------------

    page.get_by_role("tab", name="Mechanical").click()
    page.wait_for_timeout(200)

    # Main engines
    active_main_engines = [
        e for e in MAIN_ENGINES
        if any_value(e["make"], e["model"], e["type"], e["fuel_type"], e["output"], e["hours"], e["location"])
    ][:MAX_MAIN_ENGINES]

    if active_main_engines:
        main_engine_section = page.locator("div.mb-7").filter(
            has=page.locator("h2", has_text="Main Engine")
        ).first

        if main_engine_section.count() == 0:
            print("[MISS] Main Engine section not found")
        else:
            main_engine_section.scroll_into_view_if_needed()
            page.wait_for_timeout(200)

            ensure_row_count(
                main_engine_section,
                page,
                len(active_main_engines),
                "Main Engine #",
                MAX_MAIN_ENGINES
            )

            main_engine_rows = get_repeater_rows(main_engine_section, "Main Engine #")
            row_count = main_engine_rows.count()

            for i, engine in enumerate(active_main_engines):
                if i >= row_count:
                    print(f"[MISS] Main Engine #{i + 1}: row not available")
                    continue

                block = main_engine_rows.nth(i)
                block.scroll_into_view_if_needed()
                page.wait_for_timeout(200)

                fill_engine_like_block(
    block,
    page,
    engine,
    row_name=f"Engine #{i + 1}",
    output_unit="hp",
    preserve_existing_output_unit=True,
)

    # Generators
    active_generators = [
        g for g in GENERATORS
        if any_value(g["make"], g["model"], g["type"], g["fuel_type"], g["output"], g["hours"], g["location"])
    ][:MAX_GENERATORS]

    if active_generators:
        generator_section = page.locator("div.mb-7").filter(
            has=page.locator("h2", has_text="Generator")
        ).first

        if generator_section.count() == 0:
            print("[MISS] Generator section not found")
        else:
            generator_section.scroll_into_view_if_needed()
            page.wait_for_timeout(300)

            ensure_row_count(
                generator_section,
                page,
                len(active_generators),
                "Generator #",
                MAX_GENERATORS
            )

            generator_rows = get_repeater_rows(generator_section, "Generator #")
            row_count = generator_rows.count()

            for i, generator in enumerate(active_generators):
                if i >= row_count:
                    print(f"[MISS] Generator #{i + 1}: row not available")
                    continue

                block = generator_rows.nth(i)
                block.scroll_into_view_if_needed()
                page.wait_for_timeout(200)

                fill_engine_like_block(
    block,
    page,
    generator,
    row_name=f"Generator #{i + 1}"
)


        # Stabilizer
    if any_value(STABILIZER_MANUFACTURER, STABILIZER_TYPE, STABILIZER_SPEED):
        stabilizer_section = page.locator(
            "xpath=//h3[contains(normalize-space(.), 'Stabilizer')]/ancestor::div[contains(@class,'border-t')][1]"
        ).first

        if stabilizer_section.count() == 0:
            print("[MISS] Stabilizer section not found")
        else:
            if has_value(STABILIZER_MANUFACTURER):
                manufacturer_block = get_card_by_label_text(stabilizer_section, "manufacturer")
                if manufacturer_block is None:
                    print("[MISS] Stabilizer Manufacturer: card not found")
                else:
                    manufacturer_input = manufacturer_block.locator("input").first
                    fill_if_present(manufacturer_input, STABILIZER_MANUFACTURER)

            if has_value(STABILIZER_TYPE):
                type_block = get_card_by_label_text(stabilizer_section, "type")
                if type_block is None:
                    print("[MISS] Stabilizer Type: card not found")
                else:
                    type_dropdown = type_block.locator("div.ant-select").first
                    select_dropdown_by_typing(
                        type_dropdown,
                        STABILIZER_TYPE,
                        page,
                        field_name="Stabilizer Type"
                    )

            if has_value(STABILIZER_SPEED):
                speed_block = get_card_by_label_text(stabilizer_section, "speed")
                if speed_block is None:
                    print("[MISS] Stabilizer Speed: card not found")
                else:
                    speed_dropdown = speed_block.locator("div.ant-select").first
                    select_dropdown_by_typing(
                        speed_dropdown,
                        STABILIZER_SPEED,
                        page,
                        field_name="Stabilizer Speed"
                    )



    # Systems
    if any_value(
        BOW_THRUSTER,
        STERN_THRUSTER,
        STEERING,
        SHAFTS_PROPELLERS,
        SHORE_POWER,
        GEARBOX,
    ):
        systems_map = [
            ("Bow Thruster", BOW_THRUSTER),
            ("Stern Thruster", STERN_THRUSTER),
            ("Steering", STEERING),
            ("Shafts Propellers", SHAFTS_PROPELLERS),
            ("Shore Power", SHORE_POWER),
            ("Gearbox", GEARBOX),
        ]

        for label, value in systems_map:
            if has_value(value):
                block = get_card_by_label_text(page, label)

                if block is None:
                    print(f"[MISS] {label}: card not found")
                else:
                    input_box = block.locator("input").first
                    fill_if_present(input_box, value)



    # Richtext sections
    richtext_sections = [
        ("Electricity", "texteditor-contenteditable-electricity", ELECTRICITY_BULLETS),
        ("Batteries", "texteditor-contenteditable-batteries", BATTERIES_BULLETS),
        ("Battery Chargers", "texteditor-contenteditable-batteryChargers", BATTERY_CHARGERS_BULLETS),
        ("Air Conditioning", "texteditor-contenteditable-airconditioning", AIR_CONDITIONING_BULLETS),
    ]

    other_machinery_section = None

    for heading, testid, bullets in richtext_sections:
        if not has_value(bullets):
            if heading == "Other Machinery":
                other_machinery_section = page.locator("div.border-t.border-gray15.pt-8.pb-12").filter(
                    has=page.locator("h3", has_text=heading)
                ).first
            continue

        section = page.locator("div.border-t.border-gray15.pt-8.pb-12").filter(
            has=page.locator("h3", has_text=heading)
        ).first

        editor = section.locator(f"[data-testid='{testid}']").first
        editor.click(force=True)
        section.locator("[data-testid='toolbar-list-ul']").first.click()

        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")

        for i, item in enumerate(bullets):
            if not has_value(item):
                continue
            page.keyboard.insert_text(str(item))
            if i < len(bullets) - 1:
                page.keyboard.press("Enter")

        section.locator("[data-testid='texteditor-toolbar-save-button']").first.click()

        if heading == "Other Machinery":
            other_machinery_section = section



    # ---------------------------
    # EQUIPMENT TAB
    # ---------------------------

    if getattr(args, 'no_equipment', False):
        print("\n--- Equipment Tab skipped ---")
    else:
        equipment_to_fill = {
            key: EQUIPMENT_SECTIONS[key]
            for key in EQUIPMENT_SUBTAB_ORDER
            if key in EQUIPMENT_SECTIONS and any(str(l).strip() for l in EQUIPMENT_SECTIONS[key])
        }

        # Categorise raw lines into (category, [lines]) structure
        _categorized = _categorize_sections(equipment_to_fill)

        if equipment_to_fill:
            print("\n--- Equipment Tab ---")

            try:
                equipment_tab = page.get_by_role("tab", name="Equipment", exact=True)
                equipment_tab.wait_for(state="visible", timeout=8000)
                equipment_tab.scroll_into_view_if_needed()
                equipment_tab.click()
                page.wait_for_timeout(2000)  # wait for subtab list to render

                for key, lines in equipment_to_fill.items():
                    label = EQUIPMENT_SUBTAB_LABELS[key]
                    non_empty = [str(l).strip() for l in lines if str(l).strip()]
                    print(f"Filling: {label} ({len(non_empty)} lines)")

                    # Click subtab — wait up to 8s for it to appear after Equipment tab renders
                    try:
                        subtab = page.get_by_role("tab", name=label, exact=True)
                        subtab.wait_for(state="visible", timeout=8000)
                        subtab.scroll_into_view_if_needed()
                        subtab.click()
                        page.wait_for_timeout(1000)
                    except PlaywrightTimeoutError:
                        print(f"  [MISS] subtab not found: '{label}'")
                        FIELD_MISSES.append({"field": f"Equipment/{label}", "reason": "subtab not found"})
                        continue

                    # nth(1) is the active subtab panel; nth(0) is the outer Equipment section wrapper
                    panel = page.locator(".ant-tabs-tabpane-active").nth(1)

                    # The contenteditable has min-h-0 so Playwright considers it "not visible" —
                    # check it's attached and use force=True on click instead of waiting for visible
                    editor = panel.locator("[contenteditable='true']").first
                    if editor.count() == 0:
                        print(f"  [MISS] editor not found in panel: '{label}'")
                        FIELD_MISSES.append({"field": f"Equipment/{label}", "reason": "editor not found"})
                        continue

                    try:
                        structured = _categorized.get(key, [("", non_empty)])
                        write_equipment_content(panel, page, structured)
                        total = sum(len(ls) for _, ls in structured)
                        print(f"  [OK] {len(structured)} categories, {total} lines written")
                    except Exception as e:
                        print(f"  [ERROR] {label}: {e}")
                        FIELD_MISSES.append({"field": f"Equipment/{label}", "reason": str(e)})

            except PlaywrightTimeoutError:
                FIELD_MISSES.append({"field": "Equipment tab", "reason": "top-level tab not found"})
            except Exception as e:
                print(f"  [ERROR] Equipment tab: {e}")
        else:
            print("\nNo equipment sections to fill.")

    print("\n====================")
    print("RUN COMPLETE - NOT SAVING")
    print("====================")

    if DROPDOWN_MISSES:
        print("\nDropdown values not selected:")
        for miss in DROPDOWN_MISSES:
            print(f"- {miss['field']}: '{miss['value']}' -> {miss['reason']}")
    else:
        print("\nNo dropdown misses recorded.")

    if FIELD_MISSES:
        print("\nFields/cards not found:")
        for miss in FIELD_MISSES:
            print(f"- {miss['field']} -> {miss['reason']}")
    else:
        print("\nNo field misses recorded.")

    if getattr(args, 'no_review', False):
        # Called from the UI — leave the browser open for manual review & save.
        # Print a sentinel so the UI knows it can end the log stream.
        print("\n=== BROWSER OPEN — review, save, then close the window ===")
        sys.stdout.flush()
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        # User closed the browser; script exits cleanly.
    else:
        input("\nReview the page. Press Enter to close without saving...")
        browser.close()
