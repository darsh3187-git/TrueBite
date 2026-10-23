# TrueBite — AI Food Label Decoder

**Track:** Best Use of Gemma 4  
**Tagline:** Decode the label. Understand what's inside.

TrueBite is a Streamlit prototype that sends front-and-back photos of a food
package to the configured Gemma model and presents extracted label details with
evidence references and uncertainty. Deterministic application logic separately
screens marketing claims and matches selected allergens against extracted
ingredients and printed statements.

## The problem and approach

Ingredients, nutrition tables, allergen statements and marketing claims can be
difficult to read and compare on small or complex packaging. TrueBite combines
multimodal extraction with conservative local checks:

1. The app validates both uploaded images in memory and normalizes them.
2. `gemma_service.py` sends the front and back images to the configured Google
   Gen AI model and validates its JSON response against the shared schema.
3. The app displays extracted text, source image, evidence quote and
   model-estimated confidence where available.
4. `claimcheck.py` compares selected claim types with extracted fields and
   checks selected allergens against ingredient names and explicit statements.
5. The app combines the extraction and derived findings in a downloadable JSON
   report.

Gemma 4 is used for visual understanding of label images. It is responsible
only for extracting what appears in the photos; claim comparisons and
allergen-term matches are deterministic code, not additional model judgments.
The configured model ID and image-input access must be verified with the
Google API account in use—this repository does not claim that API access has
been tested.

## Architecture

| Module | Responsibility |
| --- | --- |
| `app.py` | Streamlit inputs, session state, results, evidence display and report download |
| `gemma_service.py` | Image validation/preprocessing, Google Gen AI request, parsing and safe errors |
| `analysis_schema.py` | Authoritative JSON Schema, validation and broken-evidence handling |
| `claimcheck.py` | Conservative claim comparisons and allergen matching; no API calls |
| `ingredient_service.py` | Optional curated, general ingredient explanations |
| `data/ingredient_reference.json` | Local ingredient reference data |
| `tests/` | Offline tests; no API key or live model request required |

The root `app.py` forwards to the maintained implementation in `truebite/`.
Run the setup, app, tests and optional diagnostics from the `truebite` folder.

### Public interfaces

```python
analyze_food_labels(
    front_image: bytes,
    back_image: bytes,
    allergen_preferences: list[str] | None = None,
    product_name: str | None = None,
) -> dict[str, Any]

compare_claims(analysis: dict[str, Any]) -> list[dict[str, Any]]

match_allergens(
    analysis: dict[str, Any],
    allergen_preferences: list[str],
) -> list[dict[str, Any]]
```

Images are raw bytes from in-memory uploads. They are validated and normalized
without being saved to disk. The interface accepts JPG, PNG and WEBP images
up to 12 MB each. The optional product name and allergen preferences are
context only; they do not replace image evidence.

### Shared response schema

The authoritative JSON Schema is `truebite/analysis_schema.py` (`ANALYSIS_SCHEMA`,
Draft 2020-12). A successful model response has these top-level fields:

```json
{
  "schema_version": "1.0",
  "analysis_status": "complete",
  "product_name": {
    "value": null,
    "confidence": 0.0,
    "evidence_ids": []
  },
  "front_label_claims": [],
  "ingredients": {
    "raw_text": null,
    "items": [],
    "confidence": 0.0,
    "evidence_ids": []
  },
  "nutrition": {
    "serving_size": {
      "value": null,
      "unit": null,
      "evidence_ids": [],
      "confidence": 0.0
    },
    "basis": "unknown",
    "values": [],
    "confidence": 0.0,
    "evidence_ids": []
  },
  "allergen_statements": [],
  "evidence": [],
  "unreadable_fields": [],
  "warnings": [],
  "limitations": []
}
```

The example above documents shape only; it is not sample analysis data.
Missing label text and numeric values are `null`, never invented or silently
replaced with zero. Numeric nutrition values require a unit and have an
explicit `basis` (`per_serving`, `per_100g`, `per_100ml`, `other`, or
`unknown`). Confidence is between 0 and 1, but is a model estimate, not a
calibrated probability.

Claims use `normalized_type` values `sugar_free`, `no_added_sugar`,
`low_sugar`, `high_protein`, `low_sodium`, `organic`, `gluten_free`,
`natural`, or `other`; they also identify the source image, evidence IDs,
confidence and review status. Ingredient items, nutrition values, allergen
statements and product names reference evidence IDs. Every referenced ID must
exist in `evidence`. Broken model references are removed, a warning is added,
and unsupported claims are marked `insufficient_evidence`.

Field details:

- `product_name`: `value` (`string` or `null`), `confidence`, `evidence_ids`.
- Each `front_label_claims` item: `claim_id`, `text`, `normalized_type`,
  `source_image` (`front`), `evidence_ids`, `confidence`, and `review_status`
  (`extracted` or `insufficient_evidence`).
- `ingredients`: `raw_text` (`string` or `null`), `items`, `confidence`,
  `evidence_ids`. Each item has `name`, `normalized_name`, `evidence_ids`,
  `confidence`.
- `nutrition`: `serving_size` (`value`, `unit`, `evidence_ids`, `confidence`),
  `basis`, `values`, `confidence`, `evidence_ids`. Each value has `nutrient`,
  numeric-or-null `value`, `unit`, `evidence_ids`, `confidence`. A numeric
  value requires a unit and a known basis.
- Each `allergen_statements` item: `text`, `statement_type` (`contains`,
  `may_contain`, `cross_contact`, or `other`), `mentioned_allergens`,
  `source_image`, `evidence_ids`, `confidence`.
- Each `evidence` item: unique `evidence_id`, `source_image` (`front` or
  `back`), `field`, exact model-extracted `quote`, optional `location_hint`,
  `confidence`.
- Each `unreadable_fields` item: `field`, `source_image`, `reason`,
  `attempted_text` (`string` or `null`). `warnings` and `limitations` are
  arrays of strings.

Claim comparisons use `consistent_with_extracted_data`,
`potential_discrepancy`, `insufficient_evidence`, or `not_applicable`. They
are review prompts, not regulatory or safety judgments. Allergen screening
reports explicit statement matches separately from possible ingredient-term
matches. A no-match result never means allergen-free or safe.

## Setup on Windows

Open PowerShell in the project root, then:

```powershell
cd .\truebite
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `truebite\.env` locally and set:

```dotenv
GOOGLE_API_KEY=your_google_api_key_here
GEMMA_MODEL=gemma-4-26b-a4b-it
```

Keep `.env` private. `.env.example` contains placeholders only. The app reads
the key from the environment/`.env` and does not include it in the analysis
report.

Run the app from `truebite`:

```powershell
streamlit run app.py
```

You can also start it from the project root with `streamlit run app.py`.

## Verify model access

The configured model ID, account permissions, quota and image-input support
depend on the Google API project. Verify them in the project/account's current
Google Gen AI documentation and console. Then run this optional text-only
connectivity check from `truebite`:

```powershell
python check_gemma_access.py
```

That check does **not** verify image input. To check multimodal support, run the
app and submit clear front/back photos using the configured model. A successful
request is the only evidence that the current model/account accepted that
image-analysis request. The app reports authentication/access, unavailable
model and quota failures without exposing request details.

## Tests

From the project root, run the offline suite:

```powershell
python -m pytest -q
```

The root `pytest.ini` points discovery at `truebite/tests` and adds `truebite`
to Python's import path. The tests mock Google SDK requests and do not need a
real API key. The optional connectivity script is not part of pytest
collection and is never run by the unit tests.

## Safe use and limitations

- Always verify extracted values and quotes against the original package;
  image analysis can miss small, blurry, cropped or obscured text.
- Evidence quotes are model-extracted and are not independently verified
  against the pixels by a second OCR system.
- Claim checks are deliberately conservative. In particular, a zero nutrition
  value does not prove a marketing claim, and sugar-related matches are only
  signals for review.
- Allergen matching uses a finite synonym map. A missing match does not rule
  out an allergen, cross-contact risk, manufacturing exposure or an
  unrecognized ingredient name.
- TrueBite is not medical advice, a food-safety guarantee, certification or a
  regulatory compliance assessment. Do not use it to decide whether food is
  safe for a person with an allergy.
- Uploaded photos are sent to the configured Google Gen AI service for
  analysis. Do not assume provider-side retention or deletion behavior.
- API access, quota and model availability can change. No live API request is
  made during tests, and model access has not been certified by the test suite.
