import json
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

import gemma_service
from gemma_service import TrueBiteAnalysisError


def _image_bytes():
    output = BytesIO()
    Image.new("RGB", (12, 12), "white").save(output, format="PNG")
    return output.getvalue()


def test_missing_front_image_is_rejected_before_api_request(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    with pytest.raises(TrueBiteAnalysisError, match="front image is missing"):
        gemma_service.analyze_food_labels(None, _image_bytes())


def test_invalid_image_is_rejected(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    with pytest.raises(TrueBiteAnalysisError, match="not a valid"):
        gemma_service.analyze_food_labels(b"not an image", _image_bytes())


def test_oversized_image_is_rejected(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    oversized = b"x" * (gemma_service.MAX_IMAGE_BYTES + 1)
    with pytest.raises(TrueBiteAnalysisError, match="12 MB or smaller"):
        gemma_service.analyze_food_labels(oversized, _image_bytes())


def test_malformed_model_json_is_rejected():
    with pytest.raises(TrueBiteAnalysisError, match="invalid or incomplete"):
        gemma_service._extract_json("{not json")


def test_non_json_numeric_constant_is_rejected():
    with pytest.raises(TrueBiteAnalysisError, match="invalid or incomplete"):
        gemma_service._extract_json('{"confidence": NaN}')


def test_successful_call_sends_images_and_returns_validated_contract(
    monkeypatch, analysis_factory
):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    sample = analysis_factory()
    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text=json.dumps(sample))

    fake_client = SimpleNamespace(models=FakeModels())
    monkeypatch.setattr(gemma_service.genai, "Client", lambda **kwargs: fake_client)

    result = gemma_service.analyze_food_labels(
        _image_bytes(),
        _image_bytes(),
        allergen_preferences=["milk"],
        product_name="Sample only",
    )

    assert result["schema_version"] == "1.0"
    assert captured["model"] == gemma_service.MODEL
    assert captured["config"].response_mime_type == "application/json"
    assert len(captured["contents"]) == 5


def test_api_quota_error_is_sanitized(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    class QuotaError(Exception):
        status_code = 429

    class FakeModels:
        def generate_content(self, **kwargs):
            raise QuotaError("private request details")

    monkeypatch.setattr(
        gemma_service.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(models=FakeModels()),
    )

    with pytest.raises(TrueBiteAnalysisError) as error:
        gemma_service.analyze_food_labels(_image_bytes(), _image_bytes())

    assert "quota or rate limit" in str(error.value)
    assert "private request details" not in str(error.value)
