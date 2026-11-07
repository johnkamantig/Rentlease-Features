# Portable model integration

The FastAPI service loads the matching portable export in `models/`:

- `model_metadata.json`: configuration, input order, numeric/categorical columns,
  amenity vocabulary, target transform, training provenance and package versions.
- `selected_preprocessor.joblib`: fitted sklearn ColumnTransformer, loaded with joblib.
- `selected_xgboost.ubj`: booster, loaded with `XGBRegressor.load_model()`.
- `reference_predictions.json`: three notebook reference requests and PHP predictions.

The full-pipeline joblib snapshot is no longer used. No model files were rewritten
and no deployment was performed.

## Input and prediction behavior

`ModelBundle.load(models_directory)` validates metadata, fitted components,
feature order, transformer column selections, preprocessing settings, prediction
groups and the booster's expected feature width (204 transformed features).
Startup fails with an actionable error if the matching export cannot load.

The metadata's `shared_apartment_condominium` representation maps apartment and
condominium to `apartment_condominium`; house remains `house`. These are the only
two prediction groups. Canonical combined-group requests require an explicit
subtype. Original apartment/condominium requests with a missing, blank, `unknown`
or `nan` subtype fall back to the original property type. House's missing subtype
becomes `unknown`. Subtypes stay separate from the prediction group.

The portable metadata does not include a subtype allowlist. The adapter retains
the existing API's parent/subtype validation: house/townhouse/beach_house/villa;
apartment/room; condominium/studio/loft/penthouse/condotel. It does not reinterpret
these as additional prediction groups. Unknown city and furnishing categories
are handled by the fitted encoder's `handle_unknown='ignore'` behavior.

Input columns use the metadata's exact order. Categories are stripped and
lowercased, nulls become `unknown`, and blank strings remain blank. Eight numeric
inputs are optional: null/blank values stay NaN for the fitted median imputer and
missing indicators. Invalid supplied numbers, booleans, containers, infinities,
negative physical quantities and invalid geographic coordinates are rejected.

`amenities_normalized` accepts a pipe-separated string or a string list. Terms
are stripped and deduplicated without changing case, matching the notebook's
feature builder. Vocabulary order comes directly from metadata. Missing/null
amenities yield NaN flags; explicit empty strings/lists yield zero flags.
Unknown terms and client-supplied `amenity_000` flags are ignored. This interface
expects cleaned feature values, not raw listing descriptions or amenity aliases.

Prediction calls the fitted preprocessor and then the booster. It applies
`expm1` exactly once to the booster's log prediction, preserving NumPy float32
precision before conversion to Python float and API rounding. No training
sample weights or other inverse transformations are applied at inference.

Authentication (`ML_SHARED_SECRET` bearer token), `/health`, response fields,
PHP currency, the 70%-130% range and `development-v1` are unchanged.

## Verification — 2026-11-07

All 10 tests pass, including all reference predictions both directly and through
the authenticated ASGI API, missing optional fields, group/subtype mapping,
metadata and feature-width validation, invalid requests, authentication, health,
and invalid-prediction rejection. Tests use the actual portable artifacts;
there is no deserialization bypass or mocked prediction in the reference checks.

| Original property type | Reference PHP | Service PHP before rounding |
| --- | ---: | ---: |
| Condominium | 22433.353515625 | 22433.353515625 |
| Apartment | 39733.69921875 | 39733.69921875 |
| House | 26632.958984375 | 26632.958984375 |

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

`pip check` passes. Verified runtime: Python 3.13.7, sklearn 1.6.1, XGBoost 3.4.1,
joblib 1.6.0, NumPy 2.5.4, pandas 3.0.6 on Windows. Export metadata records Python
3.13.18, sklearn 1.6.1, XGBoost 3.4.1, joblib 1.6.0, NumPy 2.4.6 and pandas 2.2.3
on Linux. Actual loading and reference agreement establish compatibility for
these supplied artifacts and cases; requirements did not need changing.

## Rollback

Previous artifacts were already located in `models/old/` when this update began.
`rentlease_model.ubj` and `rentlease_preprocessor.joblib` there are byte-identical
to the repository's tracked originals. Their SHA-256 hashes are:

- Booster: `61efa7bc91d5e553b2375b54483502dc25f7f5a8be89de6fa6f8cad25d7e3235`
- Preprocessor: `640154398ae9e9d5f6687fee1c352f8dfd48eda46926a298231cade120ef6681`

The full `validation_selected_model.joblib`, `models/old/original_xgboost_model.joblib`
and `model_versions.json` also remain available. To restore the original service,
restore `main.py` from its legacy revision and copy the matching legacy
preprocessor and booster from `models/old/` back to the paths that revision loads.
Keep the backups. Never combine a preprocessor and booster from different exports.
