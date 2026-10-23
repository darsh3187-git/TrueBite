
import json
import re
from pathlib import Path

REFERENCE_PATH = Path(__file__).parent / "data" / "ingredient_reference.json"


class IngredientReferenceError(Exception):
    """Raised when the local curated ingredient reference cannot be read."""


def load_ingredient_reference():
    """Load the curated local reference without making API requests."""
    try:
        with REFERENCE_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise IngredientReferenceError(
            "The local ingredient reference could not be loaded."
        ) from exc
    if not isinstance(data, dict):
        raise IngredientReferenceError(
            "The local ingredient reference has an invalid format."
        )
    return data


def explain_ingredient(name, reference=None):
    """Return a curated explanation for a matching ingredient."""
    if not name or not isinstance(name, str):
        return None

    reference = reference if reference is not None else load_ingredient_reference()
    normalized = re.sub(r"\s+", " ", name.strip().lower())

    for canonical, details in reference.items():
        aliases = [canonical] + details.get("common_names", [])
        for alias in aliases:
            alias = str(alias).strip().lower()
            if alias and re.search(
                rf"(?<!\w){re.escape(alias)}(?!\w)",
                normalized,
            ):
                return {
                    "matched_name": canonical,
                    **details,
                }

    return None
