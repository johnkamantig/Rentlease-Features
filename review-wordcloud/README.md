# RentLease multilingual review word cloud

Standalone local prototype using **synthetic data only**. No database, frontend, model, deployment, authentication, sentiment analysis, translation, or paid service is involved. This unauthenticated fixture API is **NOT a production authorization contract**. Bind it to localhost.

## Run (PowerShell, from repository root)

```powershell
# Only if the local environment does not exist:
py -3.11 -m venv review-wordcloud/.venv
& review-wordcloud/.venv/Scripts/python.exe -m pip install -r review-wordcloud/requirements.txt
Set-Location review-wordcloud
& .venv/Scripts/python.exe -m uvicorn src.app:app --host 127.0.0.1 --port 8001
```

Open **http://127.0.0.1:8001/**. API explorer: http://127.0.0.1:8001/docs. Stop with Ctrl+C. No Node dependencies or frontend build required. The property selector includes populated, empty, and insufficient-data examples. Select a cloud term to filter, Clear filter to restore all eligible originals, or switch themes. Back returns to the local prototype overview.

## Focused checks (from review-wordcloud)

```powershell
& .venv/Scripts/python.exe -m unittest discover -s tests -v
node tests/test_highlight.mjs
```

Python tests cover multilingual extraction, distinct-review counts, phrases and boundaries, configurable stopwords, negations, Unicode offsets, visibility and property isolation, linking, determinism, empty/insufficient data, API errors, and static viewer serving. The Node check covers the browser's Unicode span handling and malformed spans. Neither requires network or a running server.

Verified in this implementation pass: all 9 Python tests and the Node highlighting checks passed. Headless Edge confirmed 24 clickable terms, six matching parking reviews with exact highlights, reset to 12 reviews, dark theme, empty/insufficient states, and no JavaScript errors. Desktop (1440px), tablet (768px), and mobile (390px) captures had no horizontal overflow. The style inspector's only flag was the emoji intentionally retained in an original synthetic review. No Android/device tests were run.

## Files and processing contract

- `src/processor.py`: pure standard-library lexical extraction and eligibility; `Config` controls minimum mentions (2), minimum usable reviews (2), and maximum cloud terms (24).
- `src/stopwords.json`: editable English and Filipino stopwords. Negations are always retained.
- `fixtures/reviews.json`: 18 synthetic records across three sample properties; 12 eligible demo reviews, plus excluded examples.
- `src/app.py`: FastAPI wrapper and static serving.
- `web/`: accessible wrapping word buttons, light/dark styling, asynchronous selection, and safe highlighting.
- `tests/`: focused Python and JavaScript checks.

Only property reviews with explicit `published: true`, `visible: true`, and `moderation_status: "approved"` contribute. Missing flags fail closed. Blank texts are ignored; duplicate eligible IDs are rejected. Input can contain multiple properties; processing scopes it before extraction.

The processor scans original Unicode letters and combining marks, then NFKC-normalizes and case-folds each token independently while retaining its original span. Configurable bilingual stopwords, URLs, emails, handles, common phone numbers, numeric fragments, and symbols are excluded. Unigrams and adjacent bigrams are discovered without a topic dictionary. A phrase requires horizontal whitespace between retained original tokens; removed tokens, contacts, punctuation, and line breaks interrupt adjacency. `clean` and `malinis` remain independent.

Each term maps to a set of review IDs with every occurrence span. Frequency is the number of distinct IDs, so repetitions never inflate it. Terms sort by decreasing frequency then normalized lexical order; review IDs sort lexically. SHA-256 gives stable URL-safe IDs and one of five decorative color names. Font size grows with review frequency relative to the cloud maximum. No random positioning, rotation, or layout measurement is needed: normal flex wrapping prevents overlapping buttons. Long terms wrap within their button.

Offsets are **zero-based, end-exclusive Unicode code-point indices**, not UTF-8 bytes or JavaScript UTF-16 units. The browser uses `Array.from(text)` before slicing; a future React Native client must do the same or convert indices. Bigram spans include their original separating whitespace. Text is rendered with `textContent`, never review-supplied HTML. Invalid/out-of-range spans are ignored, overlapping spans are skipped, and missing spans show plain original text. Request generations prevent stale responses from replacing a newer selection.

## Routes and examples

- `GET /health`: `{"status":"ok","synthetic":true}`
- `GET /properties`: available fixture IDs and names.
- `GET /properties/{property_id}/wordcloud`: status, counts, thresholds, ranked terms, and eligible original reviews for the unfiltered view.
- `GET /properties/{property_id}/wordcloud/terms/{term_id}/reviews`: selected term and matching eligible original reviews with spans.

Unknown properties and unavailable terms return 404. Known properties return honest `empty` or `insufficient_data` states with an empty `terms` array. Insufficient properties can still display their existing original review.

Illustrative response shape (IDs/counts below explain the contract; inspect the live route for fixture values):

```json
{
  "property_id": "demo",
  "status": "ready",
  "synthetic": true,
  "eligible_review_count": 12,
  "usable_review_count": 12,
  "thresholds": {"min_review_mentions": 2, "min_usable_reviews": 2},
  "span_encoding": "unicode_code_points",
  "terms": [{"id": "t-<sha256-of-normalized-term>", "text": "parking", "review_count": 6, "review_ids": ["r01", "r02", "r03", "r06", "r09", "r12"], "color": "blue", "font_size_rem": 2.3}],
  "reviews": [{"id": "r01", "text": "Malinis ang unit, and the parking area is spacious."}]
}
```

Term-selection review entry:

```json
{"id":"r01","text":"Malinis ang unit, and the parking area is spacious.","spans":[{"start":26,"end":33}]}
```

## Limitations and later T7 integration

This is lexical matching, not semantic understanding: no stemming, spelling correction, language classifier, synonym merging, translation, sentiment, or phrase-quality model. Negation phrases can appear alongside their individual words; reading originals provides context. Stopwords and frequency thresholds need corpus evaluation; uncommon vocabulary stays discoverable but only displays when it reaches the configured threshold. Rule-based contact filtering is imperfect and only suppresses extraction: **original synthetic text is intentionally unchanged**, including sample contacts. It is not a PII redaction system. Unicode normalization is token-local and intended for Latin-script English/Filipino; unusual compatibility characters and obfuscated contacts need further evaluation. The small dataset is recomputed per request, with no persistence or pagination. Browser rendering does not claim Android/device testing.

Before T7/Supabase integration, agree on actual property-review schema and visibility/publication/moderation rules; apply authenticated property authorization and RLS before both aggregation and matching; exclude reciprocal user reviews; decide privacy/redaction policy for originals and derived vocabulary; invalidate derived counts after edits/deletions/moderation; choose the processing location without assuming another service; add pagination, versioned configuration, realistic corpus evaluation, and native React Native accessible terms/highlighting. Validate code-point conversions, exact matches, narrow layouts, and mobile accessibility using approved data. No production integration is implemented here.
