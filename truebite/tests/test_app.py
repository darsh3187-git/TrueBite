import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image
from streamlit.testing.v1 import AppTest

import gemma_service
from gemma_service import TrueBiteAnalysisError

APP_PATH = Path(__file__).parents[1] / "app.py"
EMPTY_INPUT_FINGERPRINT = hashlib.sha256(b"\0\0\0").hexdigest()
APP_TEST_TIMEOUT = 10


def _png_bytes():
    output = BytesIO()
    Image.new("RGB", (16, 16), "white").save(output, format="PNG")
    return output.getvalue()


def test_initial_page_requires_both_images_and_does_not_call_model(monkeypatch):
    def unexpected_model_call(
        front_image,
        back_image,
        allergen_preferences=None,
        product_name=None,
    ):
        assert front_image is None and back_image is None
        assert allergen_preferences is None or isinstance(allergen_preferences, list)
        assert product_name is None or isinstance(product_name, str)
        raise AssertionError("The model must not run without an explicit submission.")

    monkeypatch.setattr(gemma_service, "analyze_food_labels", unexpected_model_call)

    app = AppTest.from_file(APP_PATH, default_timeout=APP_TEST_TIMEOUT).run()

    assert not app.exception
    assert len(app.file_uploader) == 2
    assert len(app.button) == 1
    assert app.button[0].disabled
    assert any("Both package photos are required" in item.value for item in app.info)


def test_api_error_is_shown_without_rendering_a_result(monkeypatch):
    def fail_request(
        front_image,
        back_image,
        allergen_preferences=None,
        product_name=None,
    ):
        assert isinstance(front_image, bytes) and isinstance(back_image, bytes)
        assert allergen_preferences is None or isinstance(allergen_preferences, list)
        assert product_name is None or isinstance(product_name, str)
        raise TrueBiteAnalysisError("Model access failed safely.")

    monkeypatch.setattr(gemma_service, "analyze_food_labels", fail_request)
    app = AppTest.from_file(APP_PATH, default_timeout=APP_TEST_TIMEOUT).run()
    app.file_uploader[0].set_value(("front.png", _png_bytes(), "image/png"))
    app.file_uploader[1].set_value(("back.png", _png_bytes(), "image/png"))
    app.run()
    app.button[0].click().run()

    assert not app.exception
    assert any("Model access failed safely." in item.value for item in app.error)
    assert not any("Your label review" in item.value for item in app.markdown)


def test_existing_analysis_shows_eight_review_sections_and_report(
    analysis_factory,
):
    analysis = analysis_factory()
    app = AppTest.from_file(APP_PATH, default_timeout=APP_TEST_TIMEOUT)
    app.session_state["truebite_result"] = analysis
    app.session_state["truebite_result_fingerprint"] = EMPTY_INPUT_FINGERPRINT
    app.session_state["truebite_input_fingerprint"] = EMPTY_INPUT_FINGERPRINT
    app.session_state["truebite_analyzed_at"] = "2026-10-23 14:00 UTC"

    app.run()

    assert not app.exception
    assert [tab.label for tab in app.get("tabs")] == [
        "Overview",
        "Front claims",
        "Ingredients",
        "Nutrition",
        "Claim checks",
        "Allergens",
        "Evidence",
        "Warnings",
    ]
    assert len(app.get("download_button")) == 1


def test_partial_analysis_is_clearly_identified(analysis_factory):
    analysis = analysis_factory(analysis_status="partial")
    app = AppTest.from_file(APP_PATH, default_timeout=APP_TEST_TIMEOUT)
    app.session_state["truebite_result"] = analysis
    app.session_state["truebite_result_fingerprint"] = EMPTY_INPUT_FINGERPRINT
    app.session_state["truebite_input_fingerprint"] = EMPTY_INPUT_FINGERPRINT
    app.session_state["truebite_analyzed_at"] = "2026-10-23 14:00 UTC"

    app.run()

    assert not app.exception
    assert any("Partial analysis" in item.value for item in app.warning)


def test_changed_allergen_preferences_invalidate_stale_results(analysis_factory):
    app = AppTest.from_file(APP_PATH, default_timeout=APP_TEST_TIMEOUT)
    app.session_state["truebite_result"] = analysis_factory()
    app.session_state["truebite_result_fingerprint"] = EMPTY_INPUT_FINGERPRINT
    app.session_state["truebite_input_fingerprint"] = EMPTY_INPUT_FINGERPRINT
    app.session_state["truebite_analyzed_at"] = "2026-10-23 14:00 UTC"
    app.run()

    app.multiselect[0].set_value(["Milk"]).run()

    assert not app.exception
    assert len(app.get("download_button")) == 0
    assert not any("Your label review" in item.value for item in app.markdown)
