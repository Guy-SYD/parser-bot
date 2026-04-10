"""
feedback.py

Manages the feedback loop for equipment categorisation.

Two JSONL files in feedback/:
  pending.jsonl   — items the API placed in "Other", awaiting human review
  confirmed.jsonl — items the human has corrected (or confirmed as correct)

Each record in pending.jsonl:
  {"id": "...", "pdf": "...", "bucket": "...", "item": "...", "ts": "..."}

Each record in confirmed.jsonl:
  {"id": "...", "pdf": "...", "original_bucket": "...", "item": "...",
   "correct_bucket": "...", "correct_subcategory": "...",
   "confirmed_at": "...", "added_to_prompt": false}
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR     = Path(__file__).resolve().parent.parent
FEEDBACK_DIR = BASE_DIR / "feedback"
PENDING_FILE  = FEEDBACK_DIR / "pending.jsonl"
CONFIRMED_FILE = FEEDBACK_DIR / "confirmed.jsonl"


def _ensure_dir():
    FEEDBACK_DIR.mkdir(exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _append_jsonl(path: Path, record: dict):
    _ensure_dir()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_others(
    pdf_name: str,
    structured: dict[str, list[tuple[str, list[str]]]],
):
    """
    Called after API categorisation. Writes any item in an "Other" subcategory
    to pending.jsonl for human review.
    """
    _ensure_dir()

    # Load existing pending items to avoid duplicates
    existing = {r["item"] for r in _read_jsonl(PENDING_FILE)}
    # Also load confirmed so we don't re-add already-resolved items
    confirmed_items = {r["item"] for r in _read_jsonl(CONFIRMED_FILE)}

    for bucket, subcats in structured.items():
        for subcat_name, lines in subcats:
            if subcat_name != "Other":
                continue
            for item in lines:
                if item in existing or item in confirmed_items:
                    continue
                record = {
                    "id":     str(uuid.uuid4()),
                    "pdf":    pdf_name,
                    "bucket": bucket,
                    "item":   item,
                    "ts":     _now(),
                }
                _append_jsonl(PENDING_FILE, record)
                existing.add(item)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def get_pending() -> list[dict]:
    """Return all unresolved pending items."""
    pending = _read_jsonl(PENDING_FILE)
    confirmed_ids = {r["id"] for r in _read_jsonl(CONFIRMED_FILE)}
    return [r for r in pending if r["id"] not in confirmed_ids]


def get_confirmed_unsynced() -> list[dict]:
    """Return confirmed items not yet added to the prompt."""
    return [r for r in _read_jsonl(CONFIRMED_FILE) if not r.get("added_to_prompt")]


def mark_synced(item_ids: list[str]):
    """Mark confirmed items as added_to_prompt=True."""
    records = _read_jsonl(CONFIRMED_FILE)
    id_set = set(item_ids)
    updated = []
    for r in records:
        if r["id"] in id_set:
            r["added_to_prompt"] = True
        updated.append(r)
    CONFIRMED_FILE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in updated) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Confirming / correcting
# ---------------------------------------------------------------------------

def confirm_item(
    item_id: str,
    correct_bucket: str,
    correct_subcategory: str,
) -> bool:
    """
    Move an item from pending to confirmed with the correct classification.
    Returns True if the item was found in pending, False otherwise.
    """
    pending = _read_jsonl(PENDING_FILE)
    record = next((r for r in pending if r["id"] == item_id), None)
    if not record:
        return False

    confirmed_record = {
        "id":                  record["id"],
        "pdf":                 record["pdf"],
        "original_bucket":     record["bucket"],
        "item":                record["item"],
        "correct_bucket":      correct_bucket,
        "correct_subcategory": correct_subcategory,
        "confirmed_at":        _now(),
        "added_to_prompt":     False,
    }
    _append_jsonl(CONFIRMED_FILE, confirmed_record)
    return True


def discard_item(item_id: str) -> bool:
    """
    Mark an item as discarded (not equipment — should have been filtered).
    Stores with correct_bucket='DISCARD' so the prompt updater can add a
    discard example.
    """
    pending = _read_jsonl(PENDING_FILE)
    record = next((r for r in pending if r["id"] == item_id), None)
    if not record:
        return False

    confirmed_record = {
        "id":                  record["id"],
        "pdf":                 record["pdf"],
        "original_bucket":     record["bucket"],
        "item":                record["item"],
        "correct_bucket":      "DISCARD",
        "correct_subcategory": "",
        "confirmed_at":        _now(),
        "added_to_prompt":     False,
    }
    _append_jsonl(CONFIRMED_FILE, confirmed_record)
    return True
