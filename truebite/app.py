import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from claimcheck import ALLERGEN_SYNONYMS, compare_claims, match_allergens
from gemma_service import TrueBiteAnalysisError, analyze_food_labels
from ingredient_service import (
    IngredientReferenceError,
    explain_ingredient,
    load_ingredient_reference,
)

logger = logging.getLogger(__name__)
st.set_page_config(
    page_title="TrueBite | AI Food Label Decoder",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --tb-forest: #123b32;
        --tb-green: #24785b;
        --tb-mint: #d8f1e3;
        --tb-lime: #c9e769;
        --tb-paper: #f7f8f3;
    }
    .stApp {
        background:
            radial-gradient(ellipse at 8% 0%, rgba(203, 237, 211, .25), transparent 34rem),
            radial-gradient(ellipse at 92% 18%, rgba(201, 231, 105, .12), transparent 30rem),
            linear-gradient(180deg, #f7f8f3 0%, #fbfcf9 55%, #f4f7f1 100%);
        background-size: 150% 150%;
        animation: tb-background 36s ease-in-out infinite alternate;
    }
    .block-container {
        max-width: 1380px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }
    .tb-hero {
        position: relative;
        overflow: hidden;
        isolation: isolate;
        padding: 2rem 2.2rem;
        border: 1px solid rgba(226, 255, 239, .16);
        border-radius: 22px;
        background: linear-gradient(122deg, #10382f, #227958);
        color: #fff;
        margin-bottom: 1.5rem;
        box-shadow: 0 18px 45px rgba(16, 56, 47, .15);
        animation: tb-enter .55s ease-out both;
    }
    .tb-hero::before {
        content: "";
        position: absolute;
        z-index: -1;
        width: 24rem;
        height: 24rem;
        right: -7rem;
        top: -15rem;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(201, 231, 105, .25), transparent 68%);
        pointer-events: none;
        animation: tb-glow 18s ease-in-out infinite alternate;
    }
    .tb-hero h1 { color: #fff; font-size: clamp(2rem, 4vw, 3rem); }
    .tb-hero p { color: #e4f5ec; font-size: 1.05rem; max-width: 54rem; }
    .tb-eyebrow {
        color: #c9e7d1;
        font-size: .76rem;
        font-weight: 700;
        letter-spacing: .15em;
        text-transform: uppercase;
    }
    div[data-testid="stMetric"], div[data-testid="stFileUploader"] section {
        border: 1px solid rgba(24, 69, 54, .14);
        border-radius: 14px;
    }
    div[data-testid="stMetric"] { padding: .8rem; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: rgba(24, 69, 54, .14);
        border-radius: 15px;
        transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(36, 120, 91, .36);
        box-shadow: 0 8px 22px rgba(18, 59, 50, .07);
        transform: translateY(-1px);
    }
    div[data-testid="stTabs"] button {
        min-height: 2.8rem;
        font-weight: 600;
    }
    div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {
        border-radius: 12px;
        transition: transform .18s ease, box-shadow .18s ease;
    }
    div[data-testid="stButton"] button:hover,
    div[data-testid="stDownloadButton"] button:hover {
        transform: translateY(-1px);
        box-shadow: 0 7px 18px rgba(18, 59, 50, .13);
    }
    @keyframes tb-glow {
        from { transform: translate3d(0, 0, 0); }
        to { transform: translate3d(-2rem, 1.5rem, 0); }
    }
    @keyframes tb-background {
        from { background-position: 0% 0%; }
        to { background-position: 100% 50%; }
    }
    @keyframes tb-enter {
        from { opacity: 0; transform: translateY(7px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: .01ms !important;
            animation-iteration-count: 1 !important;
            scroll-behavior: auto !important;
            transition-duration: .01ms !important;
        }
    }
    @media (max-width: 640px) {
        .block-container { padding-top: 1rem; }
        .tb-hero { padding: 1.4rem; border-radius: 16px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _text(value: Any, fallback: str = "Not identified") -> str:
    if value is None or not str(value).strip():
        return fallback
    return str(value).strip()


def _confidence(value: Any) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1:
        st.caption(
            f"Model-estimated extraction confidence: {value:.0%} "
            "· Not a calibrated probability"
        )
    else:
        st.caption("Extraction confidence unavailable.")


def _render_evidence(
    evidence_ids: list[str],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    if not evidence_ids:
        st.caption("No linked image evidence was returned. Verify this field.")
        return
    for evidence_id in evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        if not evidence:
            st.caption("A referenced quote is unavailable; verify the original label.")
            continue
        image_label = str(evidence.get("source_image", "unknown")).capitalize()
        st.write(f"**Model-extracted quote · {image_label}:** “{evidence['quote']}”")
        if evidence.get("location_hint"):
            st.caption(f"Location hint: {evidence['location_hint']}")
        _confidence(evidence.get("confidence"))


def _fingerprint(
    front_bytes: bytes | None,
    back_bytes: bytes | None,
    product_name: str,
    allergen_preferences: list[str],
) -> str:
    digest = hashlib.sha256()
    digest.update(front_bytes or b"")
    digest.update(b"\0")
    digest.update(back_bytes or b"")
    digest.update(b"\0")
    digest.update(product_name.strip().encode("utf-8"))
    digest.update(b"\0")
    digest.update("\0".join(sorted(allergen_preferences)).encode("utf-8"))
    return digest.hexdigest()


def _render_allergen_results(results: list[dict[str, Any]], evidence_by_id: dict[str, dict[str, Any]]) -> None:
    for result in results:
        with st.container(border=True):
            st.write(f"**{result['allergen'].title()} · {result['status'].replace('_', ' ').title()}**")
            st.write(result["explanation"])
            for match in result["matches"]:
                st.markdown(
                    f"- **{match['status'].replace('_', ' ').title()}** — "
                    f"{match['matched_text']} ({match['source'].replace('_', ' ')})"
                )
                if match.get("statement_type"):
                    st.caption(
                        "Statement type: "
                        + str(match["statement_type"]).replace("_", " ")
                    )
                _render_evidence(match.get("evidence_ids", []), evidence_by_id)


with st.sidebar:
    st.markdown("## 🥗 TrueBite")
    st.caption("Decode the label. Understand what's inside.")
    st.divider()
    st.markdown("### Review flow")
    st.write("1. Upload both sides of one package.")
    st.write("2. Choose allergens to screen.")
    st.write("3. Request Gemma 4 analysis.")
    st.write("4. Verify evidence against the package.")
    st.divider()
    st.caption(
        "AI-assisted interpretation only. Not medical advice, a food-safety "
        "certification, or a regulatory compliance assessment."
    )

st.markdown(
    """
    <div class="tb-hero">
      <div class="tb-eyebrow">TrueBite · Food label intelligence · Gemma 4</div>
      <h1>Decode the label.<br>Understand what's inside.</h1>
      <p>Extract visible package details and flag items that need a closer look.
      Every result is presented with its evidence and uncertainty.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Start a label review")
st.write(
    "Upload clear front and back photos of the same product. Include the "
    "complete ingredient list and nutrition table where possible. Both images "
    "are required before analysis can start."
)

front_col, back_col = st.columns(2)
with front_col:
    with st.container(border=True):
        st.markdown("#### 📦 Front of package")
        st.caption("Product name and front-of-pack claims")
        front_file = st.file_uploader(
            "Choose front label photo",
            type=["jpg", "jpeg", "png", "webp"],
            key="front_upload",
            help="Accepted formats: JPG, PNG, WEBP.",
            max_upload_size=12,
        )
        if front_file:
            st.image(front_file.getvalue(), caption="Front label", use_container_width=True)
            st.success(f"Front image ready · {front_file.name}")
        else:
            st.caption("No front image uploaded yet.")

with back_col:
    with st.container(border=True):
        st.markdown("#### 🏷️ Back of package")
        st.caption("Ingredients, nutrition and allergen statements")
        back_file = st.file_uploader(
            "Choose back label photo",
            type=["jpg", "jpeg", "png", "webp"],
            key="back_upload",
            help="Accepted formats: JPG, PNG, WEBP.",
            max_upload_size=12,
        )
        if back_file:
            st.image(back_file.getvalue(), caption="Back label", use_container_width=True)
            st.success(f"Back image ready · {back_file.name}")
        else:
            st.caption("No back image uploaded yet.")

product_name_hint = st.text_input(
    "Optional product name",
    max_chars=120,
    help="Context only. The analysis will still require visible label evidence.",
)
allergen_preferences = st.multiselect(
    "Which allergens should we screen for?",
    options=[name.title() for name in ALLERGEN_SYNONYMS],
    help=(
        "This checks extracted ingredients and printed allergen statements. "
        "It cannot guarantee that a product is safe."
    ),
)

front_bytes = front_file.getvalue() if front_file else None
back_bytes = back_file.getvalue() if back_file else None
current_fingerprint = _fingerprint(
    front_bytes,
    back_bytes,
    product_name_hint,
    allergen_preferences,
)
if (
    st.session_state.get("truebite_input_fingerprint") is not None
    and st.session_state.get("truebite_input_fingerprint") != current_fingerprint
):
    for key in (
        "truebite_result",
        "truebite_analyzed_at",
        "truebite_result_fingerprint",
    ):
        st.session_state.pop(key, None)
st.session_state["truebite_input_fingerprint"] = current_fingerprint

analyze_clicked = st.button(
    "🔍 Analyze with Gemma 4",
    type="primary",
    use_container_width=True,
    disabled=not (front_bytes and back_bytes),
)
if not front_bytes or not back_bytes:
    st.info("Both package photos are required. Add the missing image to continue.")
else:
    st.caption("Images are validated in memory before being sent to the configured model.")

if analyze_clicked:
    st.session_state.pop("truebite_result", None)
    try:
        with st.spinner("Gemma 4 is reading both labels and checking the response…"):
            result = analyze_food_labels(
                front_bytes,
                back_bytes,
                allergen_preferences=allergen_preferences,
                product_name=product_name_hint.strip() or None,
            )
        st.session_state["truebite_result"] = result
        st.session_state["truebite_result_fingerprint"] = current_fingerprint
        st.session_state["truebite_analyzed_at"] = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")
    except TrueBiteAnalysisError as exc:
        st.error(str(exc))
    except Exception as exc:
        logger.error("Unexpected analysis error (%s).", type(exc).__name__)
        st.error(
            "An unexpected error occurred. Check the application log for the "
            "error type and "
            "retry with clear label photos."
        )

analysis = st.session_state.get("truebite_result")
if analysis and st.session_state.get("truebite_result_fingerprint") == current_fingerprint:
    st.divider()
    st.markdown("## Your label review")
    if analysis["analysis_status"] == "partial":
        st.warning("⚠️ Partial analysis — some label information may be missing or unclear.")
    else:
        st.success("✓ Analysis response validated against the TrueBite schema.")
    st.caption(
        f"Analysis time: {st.session_state.get('truebite_analyzed_at', 'N/A')} "
        "· AI extraction can be wrong; verify against the original package."
    )

    product = analysis["product_name"]
    st.markdown(f"### {_text(product['value'], 'Product name not readable')}")
    evidence_by_id = {
        item["evidence_id"]: item for item in analysis["evidence"]
    }
    claim_findings = compare_claims(analysis)
    allergen_findings = match_allergens(analysis, allergen_preferences)
    review_count = (
        sum(finding["status"] in {
            "potential_discrepancy",
            "insufficient_evidence",
        } for finding in claim_findings)
        + len(analysis["unreadable_fields"])
    )

    overview_columns = st.columns([1.15, 1, 1, 1])
    with overview_columns[0]:
        st.metric("Analysis status", analysis["analysis_status"].title())
    overview_columns[1].metric("Front claims", len(analysis["front_label_claims"]))
    overview_columns[2].metric("Ingredients", len(analysis["ingredients"]["items"]))
    overview_columns[3].metric("Needs review", review_count)
    st.caption(
        f"Nutrition values: {len(analysis['nutrition']['values'])} · "
        f"Unreadable fields: {len(analysis['unreadable_fields'])} · "
        f"Warnings: {len(analysis['warnings'])}"
    )
    if analysis["warnings"]:
        with st.expander("Key warnings", expanded=True):
            for warning in analysis["warnings"][:3]:
                st.warning(warning)

    (
        tab_overview,
        tab_front_claims,
        tab_ingredients,
        tab_nutrition,
        tab_comparisons,
        tab_allergens,
        tab_evidence,
        tab_warnings,
    ) = st.tabs(
        [
            "Overview",
            "Front claims",
            "Ingredients",
            "Nutrition",
            "Claim checks",
            "Allergens",
            "Evidence",
            "Warnings",
        ]
    )

    with tab_overview:
        st.markdown("### Product overview")
        st.write(f"**Product name:** {_text(product['value'], 'Not provided on the extracted label')}")
        _confidence(product["confidence"])
        _render_evidence(product["evidence_ids"], evidence_by_id)
        if analysis["analysis_status"] == "partial":
            st.info("Some fields may be missing. Review unreadable fields and warnings before relying on this extraction.")
        st.caption(
            "This dashboard separates model-extracted label information from "
            "deterministic claim and allergen screening."
        )

    with tab_front_claims:
        st.markdown("### Front-of-package claims")
        claims = analysis["front_label_claims"]
        if not claims:
            st.info("No front-label claims were provided in the extracted analysis.")
        for claim in claims:
            with st.container(border=True):
                st.markdown(f"**{claim['text']}**")
                st.caption(
                    f"Source: {claim['source_image'].title()} image · "
                    f"Type: {claim['normalized_type'].replace('_', ' ')}"
                )
                if claim["review_status"] == "insufficient_evidence":
                    st.warning("Supporting evidence is insufficient; verify this claim on the package.")
                _confidence(claim["confidence"])
                _render_evidence(claim["evidence_ids"], evidence_by_id)

    with tab_ingredients:
        st.markdown("### Ingredient list")
        try:
            ingredient_reference = load_ingredient_reference()
        except IngredientReferenceError as exc:
            ingredient_reference = {}
            st.warning(str(exc))
        if analysis["ingredients"]["raw_text"]:
            st.markdown("**Extracted original text**")
            st.write(analysis["ingredients"]["raw_text"])
        items = analysis["ingredients"]["items"]
        if not items:
            st.info("No ingredients were provided in the extracted label data.")
        for index, item in enumerate(items, start=1):
            with st.container(border=True):
                st.write(f"**{index}. {item['name']}**")
                _confidence(item["confidence"])
                _render_evidence(item["evidence_ids"], evidence_by_id)
                explanation = explain_ingredient(
                    item["name"],
                    ingredient_reference,
                )
                if explanation:
                    with st.expander("Curated ingredient reference"):
                        st.caption(explanation["category"])
                        st.write(explanation["purpose"])
                        st.write("**Review note:**", explanation["review_note"])
                        st.caption(explanation["context"])

    with tab_comparisons:
        st.markdown("### Deterministic claim comparison")
        st.caption("Screening signals only—not proof of a claim or a legal/regulatory determination.")
        if not claim_findings:
            st.info("There are no extracted claims to compare.")
        for finding in claim_findings:
            with st.container(border=True):
                st.write(f"**{_text(finding['claim_text'], 'Claim not readable')}**")
                status = finding["status"]
                if status == "potential_discrepancy":
                    st.warning(f"{status.replace('_', ' ').title()} · {finding['explanation']}")
                elif status == "consistent_with_extracted_data":
                    st.success(f"{status.replace('_', ' ').title()} · {finding['explanation']}")
                else:
                    st.info(f"{status.replace('_', ' ').title()} · {finding['explanation']}")
                _render_evidence(finding["evidence_ids"], evidence_by_id)

    with tab_nutrition:
        nutrition = analysis["nutrition"]
        serving = nutrition["serving_size"]
        st.markdown("### Nutrition facts")
        if serving["value"] is not None:
            st.caption(
                "Serving size: "
                + f"{serving['value']} {serving['unit'] or ''}".strip()
            )
        else:
            st.caption("Serving size: Not readable or not provided on the extracted label.")
        st.caption(f"Values shown: {nutrition['basis'].replace('_', ' ')}")
        if not nutrition["values"]:
            st.info("No numeric nutrition values were extracted.")
        for item in nutrition["values"]:
            with st.container(border=True):
                st.write(f"**{item['nutrient']}**")
                shown = (
                    "Not readable"
                    if item["value"] is None
                    else f"{item['value']} {item['unit']}"
                )
                st.write(shown)
                _confidence(item["confidence"])
                _render_evidence(item["evidence_ids"], evidence_by_id)

    with tab_allergens:
        st.warning(
            "No match is not proof that a product is allergen-free. Cross-contact, "
            "incomplete photos and extraction errors can be missed."
        )
        if not allergen_preferences:
            st.info("Select allergens above and run the analysis to screen for them.")
        else:
            _render_allergen_results(allergen_findings, evidence_by_id)

    with tab_evidence:
        st.markdown("### Evidence from package images")
        st.caption("Quotes below were extracted by the model and have not been independently verified against the image pixels.")
        if not analysis["evidence"]:
            st.info("No evidence quotes were provided in the analysis.")
        for evidence in analysis["evidence"]:
            with st.container(border=True):
                st.markdown(f"**Evidence {evidence['evidence_id']} · {evidence['source_image'].title()} image**")
                st.write(f"“{evidence['quote']}”")
                st.caption(f"Field: {evidence['field']}")
                if evidence["location_hint"]:
                    st.caption(f"Location hint: {evidence['location_hint']}")
                _confidence(evidence["confidence"])
        st.markdown("### Unreadable fields")
        if analysis["unreadable_fields"]:
            for item in analysis["unreadable_fields"]:
                st.warning(
                    f"**{item['field']} · {item['source_image'].title()} image:** "
                    f"{item['reason']}"
                )
                if item["attempted_text"]:
                    st.caption(f"Uncertain attempted text: {item['attempted_text']}")
        else:
            st.info("No unreadable fields were reported. This does not guarantee every detail was captured.")

    with tab_warnings:
        st.markdown("### Warnings and limitations")
        if analysis["warnings"]:
            st.markdown("**Warnings**")
            for warning in analysis["warnings"]:
                st.warning(warning)
        else:
            st.info("No additional model warnings were returned.")
        if analysis["limitations"]:
            st.markdown("**Limitations reported by the model**")
            for limitation in analysis["limitations"]:
                st.write(f"- {limitation}")
        else:
            st.caption("No further limitations were supplied by the model.")
        st.warning(
            "TrueBite is informational only. Image extraction can miss text, "
            "claim comparisons are screening signals, and no allergen match "
            "does not guarantee safety."
        )

    with tab_evidence:
        report = {
            "analysis": analysis,
            "claim_comparisons": claim_findings,
            "allergen_screening": allergen_findings,
            "allergen_preferences": allergen_preferences,
            "generated_at_utc": st.session_state["truebite_analyzed_at"],
        }
        st.download_button(
            "Download complete JSON report",
            data=json.dumps(report, indent=2, ensure_ascii=False),
            file_name="truebite_analysis.json",
            mime="application/json",
            use_container_width=True,
        )
        st.caption("Export includes the validated model extraction and the current derived screening results.")

st.divider()
st.caption(
    "Informational only · Image extraction can be wrong · Claim comparisons "
    "are screening signals · No allergen match does not guarantee safety. "
    "Always verify the original package."
)
