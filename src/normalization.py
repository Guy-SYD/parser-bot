import json
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent / "normalization_rules.json"


def load_normalization_rules():
    if not RULES_PATH.exists():
        return {
            "exact_field_replacements": {},
            "make_model_split_rules": {},
        }

    return json.loads(RULES_PATH.read_text(encoding="utf-8"))



def normalize_lookup_key(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def apply_exact_field_replacement(field_name: str, value, rules: dict):
    if value is None:
        return value

    field_rules = rules.get("exact_field_replacements", {}).get(field_name, {})
    if not field_rules:
        return value

    lookup = normalize_lookup_key(value)
    return field_rules.get(lookup, value)


def apply_make_model_split(results: dict, prefix: str, idx: int, rules: dict):
    make_key = f"{prefix}_{idx}_MAKE"
    model_key = f"{prefix}_{idx}_MODEL"

    make_value = results.get(make_key, "")
    model_value = results.get(model_key, "")

    split_rules = rules.get("make_model_split_rules", {}).get(prefix, {})
    if not split_rules:
        return

    lookup = normalize_lookup_key(make_value)

    if lookup in split_rules:
        replacement = split_rules[lookup]
        results[make_key] = replacement.get("MAKE", make_value)
        # Only override model if none was extracted; a real model (e.g. "D13") takes priority
        if not model_value:
            results[model_key] = replacement.get("MODEL", model_value)


def apply_contains_field_replacement(field_name: str, value, rules: dict):
    if value is None:
        return value

    field_rules = rules.get("contains_field_replacements", {}).get(field_name, {})
    if not field_rules:
        return value

    lookup = normalize_lookup_key(value)

    for raw_text, replacement in field_rules.items():
        if normalize_lookup_key(raw_text) in lookup:
            return replacement

    return value


def apply_normalization_rules(data: dict) -> dict:
    rules = load_normalization_rules()

    # single-field replacements
    if "BUILDER" in data:
        data["BUILDER"] = apply_exact_field_replacement("BUILDER", data.get("BUILDER", ""), rules)
        data["BUILDER"] = apply_contains_field_replacement("BUILDER", data.get("BUILDER", ""), rules)

    for i in range(1, 5):
        engine_make_key = f"ENGINE_{i}_MAKE"
        generator_make_key = f"GENERATOR_{i}_MAKE"

        if engine_make_key in data:
            data[engine_make_key] = apply_exact_field_replacement("ENGINE_MAKE", data.get(engine_make_key, ""), rules)

        if generator_make_key in data:
            data[generator_make_key] = apply_exact_field_replacement("GENERATOR_MAKE", data.get(generator_make_key, ""), rules)

    # make/model split rules
    for i in range(1, 5):
        apply_make_model_split(data, "ENGINE", i, rules)
        apply_make_model_split(data, "GENERATOR", i, rules)

    return data
