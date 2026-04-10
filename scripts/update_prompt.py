"""
update_prompt.py

Reads confirmed feedback items and injects them as new few-shot examples
into equipment_categorisation_prompt.md.

Run automatically when 5+ new confirmations accumulate (triggered by ui.py),
or manually:  python scripts/update_prompt.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from feedback import get_confirmed_unsynced, mark_synced

PROMPT_FILE = BASE_DIR / "src" / "equipment_categorisation_prompt.md"
EXAMPLES_MARKER = "## FEW-SHOT EXAMPLES"
EXAMPLES_END_MARKER = "---\n\n## HANDLING AMBIGUOUS"


def format_example(record: dict) -> str:
    if record["correct_bucket"] == "DISCARD":
        return f'"{record["item"]}" → DISCARD (not equipment)'
    return f'"{record["item"]}" → {record["correct_bucket"]} / {record["correct_subcategory"]}'


def update_prompt():
    unsynced = get_confirmed_unsynced()
    if not unsynced:
        print("No new confirmed items to add.")
        return

    prompt = PROMPT_FILE.read_text(encoding="utf-8")

    # Find the examples block closing fence
    end_idx = prompt.find("```\n\n---\n\n## HANDLING")
    if end_idx == -1:
        print("[update_prompt] Could not find injection point in prompt. Aborting.")
        return

    # The injection point is just before the closing ```
    inject_at = end_idx  # insert before the closing fence

    new_lines = "\n".join(format_example(r) for r in unsynced)
    injection = f"\n{new_lines}\n"

    updated_prompt = prompt[:inject_at] + injection + prompt[inject_at:]
    PROMPT_FILE.write_text(updated_prompt, encoding="utf-8")

    ids = [r["id"] for r in unsynced]
    mark_synced(ids)

    print(f"[update_prompt] Added {len(unsynced)} new examples to prompt.")
    for r in unsynced:
        print(f"  + {format_example(r)}")


if __name__ == "__main__":
    update_prompt()
