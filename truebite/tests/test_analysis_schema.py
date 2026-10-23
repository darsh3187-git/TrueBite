import json

import pytest

from analysis_schema import AnalysisValidationError, validate_analysis


def test_valid_analysis_is_normalized(analysis_factory):
    result = validate_analysis(analysis_factory())
    assert result["schema_version"] == "1.0"
    assert result["nutrition"]["values"][0]["unit"] == "g"


def test_missing_required_field_is_rejected(analysis_factory):
    analysis = analysis_factory()
    del analysis["allergen_statements"]
    with pytest.raises(AnalysisValidationError):
        validate_analysis(analysis)


def test_dangling_evidence_is_removed_and_claim_flagged(analysis_factory):
    analysis = analysis_factory()
    analysis["front_label_claims"][0]["evidence_ids"] = ["ev_missing"]

    result = validate_analysis(analysis)

    claim = result["front_label_claims"][0]
    assert claim["evidence_ids"] == []
    assert claim["review_status"] == "insufficient_evidence"
    assert result["warnings"]


def test_confidence_outside_range_is_rejected(analysis_factory):
    analysis = analysis_factory()
    analysis["product_name"]["confidence"] = 1.1
    with pytest.raises(AnalysisValidationError):
        validate_analysis(analysis)


def test_null_nutrition_value_and_unit_are_allowed(analysis_factory):
    analysis = analysis_factory()
    item = analysis["nutrition"]["values"][0]
    item["value"] = None
    item["unit"] = None
    assert validate_analysis(analysis)["nutrition"]["values"][0]["value"] is None


def test_numeric_nutrition_value_requires_unit(analysis_factory):
    analysis = analysis_factory()
    analysis["nutrition"]["values"][0]["unit"] = None
    with pytest.raises(AnalysisValidationError):
        validate_analysis(analysis)


def test_numeric_nutrition_requires_known_basis(analysis_factory):
    analysis = analysis_factory()
    analysis["nutrition"]["basis"] = "unknown"
    with pytest.raises(AnalysisValidationError):
        validate_analysis(analysis)


def test_duplicate_evidence_ids_are_rejected(analysis_factory):
    analysis = analysis_factory()
    analysis["evidence"][1]["evidence_id"] = "ev_front"
    with pytest.raises(AnalysisValidationError):
        validate_analysis(analysis)


def test_analysis_and_derived_report_are_json_serializable(analysis_factory):
    analysis = validate_analysis(analysis_factory())
    report = {
        "analysis": analysis,
        "claim_comparisons": [],
        "allergen_screening": [],
    }
    assert json.loads(json.dumps(report))["analysis"]["schema_version"] == "1.0"
