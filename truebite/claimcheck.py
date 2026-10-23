"""Deterministic, conservative checks over the shared analysis contract."""

import re
from typing import Any

CLAIM_STATUSES = {
    "consistent_with_extracted_data",
    "potential_discrepancy",
    "insufficient_evidence",
    "not_applicable",
}

ALLERGEN_SYNONYMS = {
    "milk": ("milk", "whey", "casein", "lactose", "milk solids"),
    "peanuts": ("peanut", "groundnut", "arachis"),
    "tree nuts": (
        "almond", "cashew", "walnut", "pistachio", "hazelnut", "pecan",
        "macadamia", "brazil nut",
    ),
    "soy": ("soy", "soya", "soybean"),
    "wheat": ("wheat", "semolina", "durum"),
    "gluten": ("gluten", "wheat", "barley", "rye", "malt"),
    "eggs": ("egg", "albumen", "albumin", "egg white", "egg yolk"),
    "fish": ("fish", "anchovy", "tuna", "salmon", "cod"),
    "shellfish": (
        "shellfish", "crustacean", "shrimp", "prawn", "crab", "lobster",
        "clam", "scallop", "oyster", "mussel",
    ),
    "sesame": ("sesame", "gingelly", "tahini"),
}

SUGAR_INGREDIENT_TERMS = (
    "sugar", "sucrose", "glucose syrup", "corn syrup", "dextrose",
    "honey", "molasses", "invert syrup",
)

CLAIM_TYPES = {
    "sugar_free",
    "no_added_sugar",
    "low_sugar",
    "high_protein",
    "low_sodium",
    "organic",
    "gluten_free",
    "natural",
    "other",
}


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _contains_term(text: str, term: str) -> bool:
    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _evidence_ids(item: dict[str, Any]) -> list[str]:
    refs = item.get("evidence_ids", [])
    return [ref for ref in refs if isinstance(ref, str)] if isinstance(refs, list) else []


def _claim_type(claim: dict[str, Any]) -> str:
    claim_type = claim.get("normalized_type")
    if claim_type in CLAIM_TYPES:
        return claim_type

    text = _normalize(claim.get("text"))
    if re.search(r"\b(no added sugar|no added sugars)\b", text):
        return "no_added_sugar"
    if re.search(r"\b(sugar[- ]free|zero sugar|no sugar)\b", text):
        return "sugar_free"
    return "other"


def _comparison(
    claim: dict[str, Any],
    status: str,
    explanation: str,
    supporting_evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "claim_id": claim.get("claim_id"),
        "claim_text": claim.get("text", ""),
        "status": status,
        "explanation": explanation,
        "evidence_ids": list(dict.fromkeys(
            _evidence_ids(claim) + (supporting_evidence_ids or [])
        )),
    }


def compare_claims(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Screen claims against extracted fields without making compliance findings."""
    if not isinstance(analysis, dict):
        raise TypeError("analysis must be a dictionary.")

    claims = analysis.get("front_label_claims", [])
    if not isinstance(claims, list):
        return []

    ingredients = analysis.get("ingredients")
    if not isinstance(ingredients, dict):
        ingredients = {}
    ingredient_items = ingredients.get("items", [])
    if not isinstance(ingredient_items, list):
        ingredient_items = []
    nutrition = analysis.get("nutrition")
    if not isinstance(nutrition, dict):
        nutrition = {}
    nutrition_values = nutrition.get("values", [])
    if not isinstance(nutrition_values, list):
        nutrition_values = []

    sugar_values = [
        item for item in nutrition_values
        if isinstance(item, dict)
        and "sugar" in _normalize(item.get("nutrient"))
        and "added" not in _normalize(item.get("nutrient"))
    ]
    findings = []

    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_type = _claim_type(claim)
        claim_evidence = _evidence_ids(claim)
        if claim.get("review_status") == "insufficient_evidence" or not claim_evidence:
            findings.append(_comparison(
                claim,
                "insufficient_evidence",
                "The claim has no valid supporting image evidence. Verify it on "
                "the original package before reviewing it.",
            ))
            continue

        if claim_type == "sugar_free":
            comparable = [
                item for item in sugar_values
                if isinstance(item.get("value"), (int, float))
                and not isinstance(item.get("value"), bool)
                and _normalize(item.get("unit")) in {
                    "g", "gram", "grams", "mg", "milligram", "milligrams",
                }
                and item.get("confidence", 0) >= 0.7
                and _evidence_ids(item)
                and nutrition.get("basis") != "unknown"
            ]
            positive = next((item for item in comparable if item["value"] > 0), None)
            if positive:
                findings.append(_comparison(
                    claim,
                    "potential_discrepancy",
                    "A sugar-related nutrition value above zero was extracted. "
                    "Check its units, serving basis, rounding and the original "
                    "label; this is not a compliance determination.",
                    _evidence_ids(positive),
                ))
            elif comparable:
                findings.append(_comparison(
                    claim,
                    "consistent_with_extracted_data",
                    "The extracted sugar value is zero, so it does not conflict "
                    "with this claim. A zero value alone does not verify the "
                    "claim or establish regulatory compliance.",
                    _evidence_ids(comparable[0]),
                ))
            else:
                findings.append(_comparison(
                    claim,
                    "insufficient_evidence",
                    "No reliably evidenced sugar value with a usable unit and "
                    "serving basis was available for comparison.",
                ))
            continue

        if claim_type == "no_added_sugar":
            ingredient_matches = []
            for item in ingredient_items:
                if not isinstance(item, dict):
                    continue
                name = _normalize(item.get("normalized_name") or item.get("name"))
                for term in SUGAR_INGREDIENT_TERMS:
                    if _contains_term(name, term):
                        ingredient_matches.append(item)
                        break
            evidenced_matches = [
                item for item in ingredient_matches
                if _evidence_ids(item) and item.get("confidence", 0) >= 0.7
            ]
            if evidenced_matches:
                findings.append(_comparison(
                    claim,
                    "potential_discrepancy",
                    "A sugar-related ingredient term appears in the extracted "
                    "ingredient list. Review its exact role and the original "
                    "package; this is not a compliance determination.",
                    _evidence_ids(evidenced_matches[0]),
                ))
            else:
                findings.append(_comparison(
                    claim,
                    "insufficient_evidence",
                    "The extracted ingredient data cannot establish whether "
                    "sugars were added. A missing match is not proof of absence.",
                ))
            continue

        if claim_type == "other":
            status = "not_applicable"
            explanation = (
                "No deterministic comparison rule is defined for this claim."
            )
        else:
            status = "insufficient_evidence"
            explanation = (
                "This claim may require certification, jurisdiction-specific "
                "definitions or information not visible in these photos."
            )
        findings.append(_comparison(claim, status, explanation))

    return findings


def _analysis_incomplete(analysis: dict[str, Any]) -> bool:
    return (
        analysis.get("analysis_status") != "complete"
        or bool(analysis.get("unreadable_fields"))
    )


def match_allergens(
    analysis: dict[str, Any],
    allergen_preferences: list[str],
) -> list[dict[str, Any]]:
    """Match preferences to extracted ingredients and printed statements."""
    if not isinstance(analysis, dict):
        raise TypeError("analysis must be a dictionary.")
    if not isinstance(allergen_preferences, list):
        raise TypeError("allergen_preferences must be a list.")

    ingredients = analysis.get("ingredients")
    if not isinstance(ingredients, dict):
        ingredients = {}
    items = ingredients.get("items", [])
    if not isinstance(items, list):
        items = []
    raw_text = _normalize(ingredients.get("raw_text"))
    statements = analysis.get("allergen_statements", [])
    if not isinstance(statements, list):
        statements = []

    results = []
    for preference in allergen_preferences:
        allergen = _normalize(preference)
        terms = ALLERGEN_SYNONYMS.get(allergen)
        if not terms:
            results.append({
                "allergen": allergen,
                "status": "incomplete_information",
                "matches": [],
                "explanation": "This preference is not in the documented synonym map.",
            })
            continue

        matches = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = _normalize(item.get("normalized_name") or item.get("name"))
            matched_term = next(
                (term for term in terms if _contains_term(name, term)),
                None,
            )
            if matched_term:
                matches.append({
                    "matched_text": str(item.get("name", matched_term)),
                    "matched_term": matched_term,
                    "source": "ingredient",
                    "evidence_ids": _evidence_ids(item),
                    "status": "possible_match",
                    "explanation": (
                        "This extracted ingredient term may be associated with "
                        "the selected allergen; verify the original label."
                    ),
                })
        if raw_text:
            raw_match = next(
                (term for term in terms if _contains_term(raw_text, term)),
                None,
            )
            if raw_match and not any(
                match["matched_term"] == raw_match for match in matches
            ):
                matches.append({
                    "matched_text": raw_match,
                    "matched_term": raw_match,
                    "source": "ingredient_text",
                    "evidence_ids": _evidence_ids(ingredients),
                    "status": "possible_match",
                    "explanation": (
                        "This term appears in the extracted ingredient text; "
                        "verify the original label."
                    ),
                })

        for statement in statements:
            if not isinstance(statement, dict):
                continue
            text = _normalize(statement.get("text"))
            mentioned = statement.get("mentioned_allergens", [])
            if not isinstance(mentioned, list):
                mentioned = []
            combined = " ".join([text] + [_normalize(name) for name in mentioned])
            matched_term = next(
                (term for term in terms if _contains_term(combined, term)),
                None,
            )
            if matched_term:
                statement_type = statement.get("statement_type", "other")
                matches.append({
                    "matched_text": str(statement.get("text", matched_term)),
                    "matched_term": matched_term,
                    "source": "allergen_statement",
                    "statement_type": statement_type,
                    "evidence_ids": _evidence_ids(statement),
                    "status": "explicit_statement",
                    "explanation": (
                        "An extracted allergen statement mentions this term. "
                        "Read the statement type and original package carefully."
                    ),
                })

        if matches:
            status = "matches_found"
            explanation = (
                "One or more extracted label terms require review. This result "
                "does not determine allergen safety."
            )
        elif _analysis_incomplete(analysis):
            status = "incomplete_information"
            explanation = (
                "No match was found in the extracted text, but parts of the "
                "label may be unreadable or the analysis is incomplete."
            )
        else:
            status = "no_match_found"
            explanation = (
                "No matching term was found in the extracted fields. This does "
                "not prove the product is allergen-free or safe."
            )

        results.append({
            "allergen": allergen,
            "status": status,
            "matches": matches,
            "explanation": explanation,
        })

    return results
