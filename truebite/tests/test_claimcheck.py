from claimcheck import compare_claims, match_allergens


def test_positive_sugar_value_flags_reviewable_discrepancy(analysis_factory):
    findings = compare_claims(analysis_factory())
    assert findings[0]["status"] == "potential_discrepancy"
    assert "ev_nutrition" in findings[0]["evidence_ids"]


def test_zero_sugar_is_only_consistent_not_verified(analysis_factory):
    analysis = analysis_factory()
    analysis["nutrition"]["values"][0]["value"] = 0

    finding = compare_claims(analysis)[0]

    assert finding["status"] == "consistent_with_extracted_data"
    assert "does not verify" in finding["explanation"]


def test_claim_without_evidence_is_insufficient(analysis_factory):
    analysis = analysis_factory()
    analysis["front_label_claims"][0]["evidence_ids"] = []

    finding = compare_claims(analysis)[0]

    assert finding["status"] == "insufficient_evidence"


def test_no_added_sugar_claim_compares_evidenced_ingredients(analysis_factory):
    analysis = analysis_factory()
    analysis["front_label_claims"][0]["text"] = "No added sugar"
    analysis["front_label_claims"][0]["normalized_type"] = "no_added_sugar"
    analysis["ingredients"]["items"].append({
        "name": "Sugar",
        "normalized_name": "sugar",
        "evidence_ids": ["ev_ingredient"],
        "confidence": 0.9,
    })

    assert compare_claims(analysis)[0]["status"] == "potential_discrepancy"


def test_unsupported_claim_needs_additional_evidence(analysis_factory):
    analysis = analysis_factory()
    analysis["front_label_claims"][0]["normalized_type"] = "organic"
    assert compare_claims(analysis)[0]["status"] == "insufficient_evidence"


def test_allergen_match_in_ingredient_and_explicit_statement(analysis_factory):
    results = match_allergens(analysis_factory(), ["Milk"])
    result = results[0]

    assert result["status"] == "matches_found"
    assert {match["source"] for match in result["matches"]} == {
        "ingredient",
        "allergen_statement",
    }


def test_synonym_matching_handles_boundary_without_substring_false_positive(analysis_factory):
    analysis = analysis_factory()
    analysis["ingredients"]["items"] = [{
        "name": "Eggplant",
        "normalized_name": "eggplant",
        "evidence_ids": ["ev_ingredient"],
        "confidence": 0.9,
    }]
    analysis["ingredients"]["raw_text"] = "Eggplant"
    analysis["allergen_statements"] = []

    result = match_allergens(analysis, ["Eggs"])[0]

    assert result["status"] == "no_match_found"
    assert result["matches"] == []
    assert "does not prove" in result["explanation"]


def test_partial_analysis_without_match_is_incomplete(analysis_factory):
    analysis = analysis_factory(analysis_status="partial")
    analysis["ingredients"]["items"] = []
    analysis["ingredients"]["raw_text"] = None
    analysis["allergen_statements"] = []

    assert match_allergens(analysis, ["Peanuts"])[0]["status"] == "incomplete_information"
