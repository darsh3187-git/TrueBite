from copy import deepcopy

import pytest


@pytest.fixture
def analysis_factory():
    base = {
        "schema_version": "1.0",
        "analysis_status": "complete",
        "product_name": {
            "value": "Sample only",
            "confidence": 0.95,
            "evidence_ids": ["ev_front"],
        },
        "front_label_claims": [
            {
                "claim_id": "claim_001",
                "text": "Sugar free",
                "normalized_type": "sugar_free",
                "source_image": "front",
                "evidence_ids": ["ev_claim"],
                "confidence": 0.95,
                "review_status": "extracted",
            }
        ],
        "ingredients": {
            "raw_text": "Whey, sugar",
            "items": [
                {
                    "name": "Whey",
                    "normalized_name": "whey",
                    "evidence_ids": ["ev_ingredient"],
                    "confidence": 0.94,
                }
            ],
            "confidence": 0.9,
            "evidence_ids": ["ev_ingredient"],
        },
        "nutrition": {
            "serving_size": {
                "value": 30,
                "unit": "g",
                "evidence_ids": ["ev_nutrition"],
                "confidence": 0.91,
            },
            "basis": "per_serving",
            "values": [
                {
                    "nutrient": "Total sugars",
                    "value": 2.5,
                    "unit": "g",
                    "evidence_ids": ["ev_nutrition"],
                    "confidence": 0.92,
                }
            ],
            "confidence": 0.91,
            "evidence_ids": ["ev_nutrition"],
        },
        "allergen_statements": [
            {
                "text": "Contains milk",
                "statement_type": "contains",
                "mentioned_allergens": ["milk"],
                "source_image": "back",
                "evidence_ids": ["ev_allergen"],
                "confidence": 0.96,
            }
        ],
        "evidence": [
            {
                "evidence_id": evidence_id,
                "source_image": source,
                "field": field,
                "quote": quote,
                "location_hint": None,
                "confidence": 0.95,
            }
            for evidence_id, source, field, quote in [
                ("ev_front", "front", "product_name", "Sample only"),
                ("ev_claim", "front", "front_label_claims", "Sugar free"),
                ("ev_ingredient", "back", "ingredients", "Whey"),
                ("ev_nutrition", "back", "nutrition", "Total sugars 2.5 g"),
                ("ev_allergen", "back", "allergen_statements", "Contains milk"),
            ]
        ],
        "unreadable_fields": [],
        "warnings": [],
        "limitations": [],
    }

    def make_analysis(**updates):
        result = deepcopy(base)
        result.update(updates)
        return result

    return make_analysis
