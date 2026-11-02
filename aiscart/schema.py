"""Extraction schema and prompt for the AI's Cart screenshot-to-JSON test."""
import json

FLAGS = [
    "renewal_price_not_shown",
    "multi_year_upfront",
    "trial_converts_to_paid",
    "price_changes_after_intro",
    "text_cut_off",
    "terms_behind_link_or_login",
    "totals_do_not_add_up",
    "other",
]

FIELD = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["observed", "inferred", "unknown"]},
        "value": {"type": ["string", "null"]},
        "evidence": {"type": "string"},
    },
    "required": ["status", "value", "evidence"],
    "additionalProperties": False,
}

ITEM_FIELDS = ["name", "quantity", "term", "line_total"]
TOP_FIELDS = [
    "merchant", "currency", "subtotal", "discounts", "tax", "total_due_now",
    "renewal_terms", "trial_terms", "cancellation_terms", "other_conditions",
]

SCHEMA = {
    "type": "object",
    "properties": {
        **{k: FIELD for k in ["merchant", "currency"]},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {k: FIELD for k in ITEM_FIELDS},
                "required": ITEM_FIELDS,
                "additionalProperties": False,
            },
        },
        **{k: FIELD for k in TOP_FIELDS if k not in ("merchant", "currency")},
        "uncertainty_flags": {"type": "array", "items": {"type": "string", "enum": FLAGS}},
    },
    "required": ["merchant", "currency", "line_items", *[k for k in TOP_FIELDS if k not in ("merchant", "currency")],
                 "uncertainty_flags"],
    "additionalProperties": False,
}

# The structure written out in the prompt itself, so the playground (which can't enforce SCHEMA) sees the field names.
_F = {"status": "observed | inferred | unknown", "value": "text, or null when unknown", "evidence": "quote from the screen, or how it was derived"}
TEMPLATE = {
    "merchant": _F, "currency": _F,
    "line_items": [{k: _F for k in ITEM_FIELDS}],
    **{k: _F for k in TOP_FIELDS if k not in ("merchant", "currency")},
    "uncertainty_flags": [],
}

SYSTEM_PROMPT = f"""You read checkout and subscription screenshots for AI's Cart. Extract only what the screenshot supports.

Every field has a status, a value and evidence:
- observed: the value is visible as text. Quote the visible text in evidence.
- inferred: you derived it from visible information. Say how in evidence.
- unknown: not visible or not readable. Set value to null.

Rules:
- Never guess prices, renewal amounts, dates or terms. If it is not on screen, it is unknown.
- Copy money exactly as shown, with its currency symbol.
- One line_items entry per cart row.
- Add uncertainty_flags that apply, chosen only from: {", ".join(FLAGS)}.
- Return only JSON in exactly the structure below. Every field must appear, with these exact names. Add no other fields. No commentary.

{json.dumps(TEMPLATE, indent=2)}"""

DEFAULT_QUESTION = "Extract the facts from this checkout screenshot."
