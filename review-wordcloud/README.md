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

- `src/processor.py`: lexical extraction and eligibility. Term counting uses scikit-learn `CountVectorizer`; `Config` controls minimum mentions (2), minimum usable reviews (2), and maximum cloud terms (24).
- `src/stopwords.json`: editable English and Filipino stopwords. Negations are always retained.
- `fixtures/reviews.json`: 18 synthetic records across three sample properties; 12 eligible demo reviews, plus excluded examples.
- `src/app.py`: FastAPI wrapper and static serving.
- `web/`: accessible wrapping word buttons, light/dark styling, asynchronous selection, and safe highlighting.
- `tests/`: focused Python and JavaScript checks.

Only property reviews with explicit `published: true`, `visible: true`, and `moderation_status: "approved"` contribute. Missing flags fail closed. Blank texts are ignored; duplicate eligible IDs are rejected. Input can contain multiple properties; processing scopes it before extraction.

The processor scans original Unicode letters and combining marks, then NFKC-normalizes and case-folds each token independently while retaining its original span. Configurable bilingual stopwords, URLs, emails, handles, common phone numbers, numeric fragments, and symbols are excluded. Counting is **CountVectorizer-based document frequency**: `CountVectorizer(ngram_range=(1, 2), binary=True, min_df=2)` over the cleaned reviews (counts only, no TF-IDF), so a term counts once per review however often it repeats, and terms found in fewer than `min_df` reviews are dropped. Unigrams and bigrams are discovered without a topic dictionary. The vectorizer's preprocessor performs the noise removal and NFKC/casefold, and its token pattern only sees letter/mark tokens. **Bigrams are formed after stopword removal**, so `room was very clean` yields `room clean`. Contacts, punctuation, line breaks, digit/underscore fragments and one-letter words still interrupt adjacency; only removed stopwords do not. `clean` and `malinis` remain independent. CountVectorizer returns no positions, so a small span finder re-locates each selected term in the original text with the same scanner.

Each term maps to a set of review IDs with every occurrence span. Frequency is the number of distinct IDs, so repetitions never inflate it. Terms sort by decreasing frequency then normalized lexical order; review IDs sort lexically. SHA-256 gives stable URL-safe IDs and one of five decorative color names. Font size grows with review frequency relative to the cloud maximum. No random positioning, rotation, or layout measurement is needed: normal flex wrapping prevents overlapping buttons. Long terms wrap within their button.

Offsets are **zero-based, end-exclusive Unicode code-point indices**, not UTF-8 bytes or JavaScript UTF-16 units. The browser uses `Array.from(text)` before slicing; a future React Native client must do the same or convert indices. Bigram spans run from the first word's start to the second word's end, including the original separating whitespace and any removed stopwords between them (`Room was very clean` for `room clean`). Text is rendered with `textContent`, never review-supplied HTML. Invalid/out-of-range spans are ignored, overlapping spans are skipped, and missing spans show plain original text. Request generations prevent stale responses from replacing a newer selection.

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


## Prepared production bridge - November 10, 2026

The standalone fixture API above remains unchanged and synthetic. New root `wordcloud_api.py` mounts protected POST `/wordcloud` in existing `main:app`; it accepts only Edge-supplied property/review IDs, original bodies and corpus comparison version. It reuses this directory's unmodified Processor.cloud/matching and stopwords, with a request-local index to avoid redundant extraction. Only the Processor class is cached; no review corpus/results are retained across requests. Lazy NLP loading keeps absent processor assets from breaking existing ML startup.

Set a server-only `NLP_SHARED_SECRET`, distinct from `ML_SHARED_SECRET`, on Python and the new Supabase review-wordcloud Edge Function. Missing or duplicate ML/NLP secrets fail NLP closed. Edge verifies actual user sessions and reads every approved property-review page through caller-JWT T7A RPCs; no reciprocal feedback, raw-table/service-role bypass or arbitrary mobile review text. Edge rechecks the corpus/session after processing. The native app sends only propertyId and never receives either secret.

Deploy nothing automatically. Separately release root main.py/wordcloud_api.py and existing processor.py/stopwords.json through the current Render service; confirm its start command uses main:app (no Render configuration is tracked). Requirements, model artifacts, /health and /predict remain unchanged. Edge environment: NLP_API_URL points to the existing HTTPS service; NLP_SHARED_SECRET matches Python. No new paid service, SQL migration or dependency. Shared-host CPU/load and hosted caller-JWT/prediction acceptance are still required before frontend release.

One NLP computation per Python process; 4 MiB input, 10,020 rows, 500,000 text characters and 2,000 characters per text. Edge applies matching/stricter UTF-16 and response/time limits. Oversized corpora reject entirely, never produce partial frequencies. Rating-only rows remain in eligible counts but not extracted terms. Original text and code-point offsets are unchanged; colors are decorative and contact filtering is not PII redaction. T7A pagination is not a transactional snapshot; a moderation change after the last scan may remain visible until the next native refresh. No long-lived result cache.

Focused validation: 15 Python tests pass (six protected bridge/ML-route tests, seven processor and two fixture API tests). ML-route tests stub model dependencies and do not claim fitted inference evaluation. Frontend companion has 28 focused passing cases including actual Python-to-Edge/native response validation. Native/hosted production processing is unverified; no deployment, production data, secrets, commit or push occurred.
