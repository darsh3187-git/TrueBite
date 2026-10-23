"""Shared response contract and validation for TrueBite analyses."""

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "1.0"

ANALYSIS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "analysis_status",
        "product_name",
        "front_label_claims",
        "ingredients",
        "nutrition",
        "allergen_statements",
        "evidence",
        "unreadable_fields",
        "warnings",
        "limitations",
    ],
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION},
        "analysis_status": {"enum": ["complete", "partial", "failed"]},
        "product_name": {"$ref": "#/$defs/extracted_text"},
        "front_label_claims": {
            "type": "array",
            "items": {"$ref": "#/$defs/claim"},
        },
        "ingredients": {"$ref": "#/$defs/ingredients"},
        "nutrition": {"$ref": "#/$defs/nutrition"},
        "allergen_statements": {
            "type": "array",
            "items": {"$ref": "#/$defs/allergen_statement"},
        },
        "evidence": {
            "type": "array",
            "items": {"$ref": "#/$defs/evidence"},
        },
        "unreadable_fields": {
            "type": "array",
            "items": {"$ref": "#/$defs/unreadable_field"},
        },
        "warnings": {"$ref": "#/$defs/string_list"},
        "limitations": {"$ref": "#/$defs/string_list"},
    },
    "$defs": {
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "evidence_ids": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "uniqueItems": True,
        },
        "extracted_text": {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "confidence", "evidence_ids"],
            "properties": {
                "value": {"type": ["string", "null"]},
                "confidence": {"$ref": "#/$defs/confidence"},
                "evidence_ids": {"$ref": "#/$defs/evidence_ids"},
            },
        },
        "claim": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "claim_id",
                "text",
                "normalized_type",
                "source_image",
                "evidence_ids",
                "confidence",
                "review_status",
            ],
            "properties": {
                "claim_id": {"type": "string", "minLength": 1},
                "text": {"type": "string", "minLength": 1},
                "normalized_type": {
                    "enum": [
                        "sugar_free",
                        "no_added_sugar",
                        "low_sugar",
                        "high_protein",
                        "low_sodium",
                        "organic",
                        "gluten_free",
                        "natural",
                        "other",
                    ]
                },
                "source_image": {"const": "front"},
                "evidence_ids": {"$ref": "#/$defs/evidence_ids"},
                "confidence": {"$ref": "#/$defs/confidence"},
                "review_status": {
                    "enum": ["extracted", "insufficient_evidence"]
                },
            },
        },
        "ingredient_item": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "normalized_name", "evidence_ids", "confidence"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "normalized_name": {"type": "string", "minLength": 1},
                "evidence_ids": {"$ref": "#/$defs/evidence_ids"},
                "confidence": {"$ref": "#/$defs/confidence"},
            },
        },
        "ingredients": {
            "type": "object",
            "additionalProperties": False,
            "required": ["raw_text", "items", "confidence", "evidence_ids"],
            "properties": {
                "raw_text": {"type": ["string", "null"]},
                "items": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/ingredient_item"},
                },
                "confidence": {"$ref": "#/$defs/confidence"},
                "evidence_ids": {"$ref": "#/$defs/evidence_ids"},
            },
        },
        "serving_size": {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "unit", "evidence_ids", "confidence"],
            "properties": {
                "value": {"type": ["number", "string", "null"]},
                "unit": {"type": ["string", "null"]},
                "evidence_ids": {"$ref": "#/$defs/evidence_ids"},
                "confidence": {"$ref": "#/$defs/confidence"},
            },
            "allOf": [
                {
                    "if": {"properties": {"value": {"type": "number"}}},
                    "then": {"properties": {"unit": {"type": "string", "minLength": 1}}},
                }
            ],
        },
        "nutrient": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "nutrient",
                "value",
                "unit",
                "evidence_ids",
                "confidence",
            ],
            "properties": {
                "nutrient": {"type": "string", "minLength": 1},
                "value": {"type": ["number", "null"]},
                "unit": {"type": ["string", "null"]},
                "evidence_ids": {"$ref": "#/$defs/evidence_ids"},
                "confidence": {"$ref": "#/$defs/confidence"},
            },
            "allOf": [
                {
                    "if": {"properties": {"value": {"type": "number"}}},
                    "then": {"properties": {"unit": {"type": "string", "minLength": 1}}},
                }
            ],
        },
        "nutrition": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "serving_size",
                "basis",
                "values",
                "confidence",
                "evidence_ids",
            ],
            "properties": {
                "serving_size": {"$ref": "#/$defs/serving_size"},
                "basis": {
                    "enum": [
                        "per_serving",
                        "per_100g",
                        "per_100ml",
                        "other",
                        "unknown",
                    ]
                },
                "values": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/nutrient"},
                },
                "confidence": {"$ref": "#/$defs/confidence"},
                "evidence_ids": {"$ref": "#/$defs/evidence_ids"},
            },
        },
        "allergen_statement": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "text",
                "statement_type",
                "mentioned_allergens",
                "source_image",
                "evidence_ids",
                "confidence",
            ],
            "properties": {
                "text": {"type": "string", "minLength": 1},
                "statement_type": {
                    "enum": ["contains", "may_contain", "cross_contact", "other"]
                },
                "mentioned_allergens": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
                "source_image": {"enum": ["front", "back"]},
                "evidence_ids": {"$ref": "#/$defs/evidence_ids"},
                "confidence": {"$ref": "#/$defs/confidence"},
            },
        },
        "evidence": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "evidence_id",
                "source_image",
                "field",
                "quote",
                "location_hint",
                "confidence",
            ],
            "properties": {
                "evidence_id": {"type": "string", "minLength": 1},
                "source_image": {"enum": ["front", "back"]},
                "field": {"type": "string", "minLength": 1},
                "quote": {"type": "string", "minLength": 1},
                "location_hint": {"type": ["string", "null"]},
                "confidence": {"$ref": "#/$defs/confidence"},
            },
        },
        "unreadable_field": {
            "type": "object",
            "additionalProperties": False,
            "required": ["field", "source_image", "reason", "attempted_text"],
            "properties": {
                "field": {"type": "string", "minLength": 1},
                "source_image": {"enum": ["front", "back"]},
                "reason": {"type": "string", "minLength": 1},
                "attempted_text": {"type": ["string", "null"]},
            },
        },
        "string_list": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


class AnalysisValidationError(ValueError):
    """Raised when model output cannot meet the shared response contract."""


def _all_referenced_evidence_ids(analysis: dict[str, Any]) -> list[list[str]]:
    references: list[list[str]] = []
    product_name = analysis.get("product_name")
    if isinstance(product_name, dict):
        references.append(product_name.get("evidence_ids", []))

    for claim in analysis.get("front_label_claims", []):
        if isinstance(claim, dict):
            references.append(claim.get("evidence_ids", []))

    ingredients = analysis.get("ingredients")
    if isinstance(ingredients, dict):
        references.append(ingredients.get("evidence_ids", []))
        for item in ingredients.get("items", []):
            if isinstance(item, dict):
                references.append(item.get("evidence_ids", []))

    nutrition = analysis.get("nutrition")
    if isinstance(nutrition, dict):
        references.append(nutrition.get("evidence_ids", []))
        serving_size = nutrition.get("serving_size")
        if isinstance(serving_size, dict):
            references.append(serving_size.get("evidence_ids", []))
        for item in nutrition.get("values", []):
            if isinstance(item, dict):
                references.append(item.get("evidence_ids", []))

    for statement in analysis.get("allergen_statements", []):
        if isinstance(statement, dict):
            references.append(statement.get("evidence_ids", []))
    return [ids for ids in references if isinstance(ids, list)]


def normalize_evidence_references(analysis: dict[str, Any]) -> dict[str, Any]:
    """Drop broken references and flag claims that no longer have evidence."""
    normalized = deepcopy(analysis)
    evidence = normalized.get("evidence", [])
    evidence_ids = {
        item.get("evidence_id")
        for item in evidence
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    missing_ids = {
        evidence_id
        for refs in _all_referenced_evidence_ids(normalized)
        for evidence_id in refs
        if isinstance(evidence_id, str) and evidence_id not in evidence_ids
    }
    if not missing_ids:
        return normalized

    def clean_refs(value: Any) -> None:
        if isinstance(value, dict):
            refs = value.get("evidence_ids")
            if isinstance(refs, list):
                value["evidence_ids"] = [
                    evidence_id
                    for evidence_id in refs
                    if evidence_id in evidence_ids
                ]
            for child in value.values():
                clean_refs(child)
        elif isinstance(value, list):
            for child in value:
                clean_refs(child)

    clean_refs(normalized)
    for claim in normalized.get("front_label_claims", []):
        if isinstance(claim, dict) and not claim.get("evidence_ids"):
            claim["review_status"] = "insufficient_evidence"
    normalized.setdefault("warnings", []).append(
        "Some model-provided evidence references were not found; affected "
        "items require manual verification."
    )
    return normalized


def validate_analysis(analysis: Any) -> dict[str, Any]:
    """Validate the schema and cross-references, returning a safe normalized copy."""
    if not isinstance(analysis, dict):
        raise AnalysisValidationError("Analysis must be a JSON object.")

    schema_errors = sorted(
        Draft202012Validator(ANALYSIS_SCHEMA).iter_errors(analysis),
        key=lambda error: list(error.absolute_path),
    )
    if schema_errors:
        raise AnalysisValidationError("Analysis does not match the required schema.")

    evidence_ids = [item["evidence_id"] for item in analysis["evidence"]]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise AnalysisValidationError("Evidence IDs must be unique.")

    claim_ids = [claim["claim_id"] for claim in analysis["front_label_claims"]]
    if len(claim_ids) != len(set(claim_ids)):
        raise AnalysisValidationError("Claim IDs must be unique.")

    nutrition = analysis["nutrition"]
    if (
        nutrition["basis"] == "unknown"
        and any(item["value"] is not None for item in nutrition["values"])
    ):
        raise AnalysisValidationError(
            "Numeric nutrition values require a known serving basis."
        )

    normalized = normalize_evidence_references(analysis)
    errors = sorted(
        Draft202012Validator(ANALYSIS_SCHEMA).iter_errors(normalized),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise AnalysisValidationError("Analysis does not match the required schema.")

    evidence_ids = [item["evidence_id"] for item in normalized["evidence"]]

    for refs in _all_referenced_evidence_ids(normalized):
        if any(evidence_id not in evidence_ids for evidence_id in refs):
            raise AnalysisValidationError("An evidence reference is invalid.")

    return normalized
