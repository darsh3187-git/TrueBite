
import pytest

import ingredient_service
from ingredient_service import (
    IngredientReferenceError,
    explain_ingredient,
    load_ingredient_reference,
)


def test_reference_loads():
    reference = load_ingredient_reference()
    assert isinstance(reference, dict)
    assert "sugar" in reference


def test_sugar_explanation():
    result = explain_ingredient("Sugar")
    assert result is not None
    assert result["category"] == "Sweetener"


def test_alias_lookup():
    result = explain_ingredient("Sodium benzoate")
    assert result is not None
    assert result["matched_name"] == "sodium benzoate"


def test_unknown_ingredient():
    assert explain_ingredient("unknown sample ingredient") is None


def test_invalid_reference_file_is_reported(monkeypatch, tmp_path):
    reference_path = tmp_path / "ingredient_reference.json"
    reference_path.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(ingredient_service, "REFERENCE_PATH", reference_path)

    with pytest.raises(IngredientReferenceError):
        load_ingredient_reference()
