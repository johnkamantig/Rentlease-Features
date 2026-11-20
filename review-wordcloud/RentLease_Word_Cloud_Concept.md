# RentLease — NLP Property Review Word Cloud Concept

## 1. Purpose

I am developing **RentLease**, a React Native + Expo rental marketplace application for our undergraduate thesis. I want to discuss and refine our proposed **NLP Review Word Cloud** feature before implementation.

The feature should help prospective tenants quickly understand **what previous renters frequently mention about a specific property**. It is not intended to classify reviews as positive or negative or to generate AI summaries. It is a frequency-based visualization connected to the original reviews.

**Visual references:** I will send **two concept photos** showing how I want the word cloud and the review-selection interaction to look. Please examine both photos and use them as UI references when refining the design; they are inspiration, not a requirement to copy every detail. We should agree on the concept and interaction before finalizing the implementation.

## 2. Proposed UI and User Experience

The word cloud will appear in the **Property Reviews** section of a property's details screen in the tenant-facing RentLease app.

- Display a compact, responsive cloud of words and short phrases, inspired by the concept photos.
- **Larger words** indicate that **more distinct eligible reviews** mention that term; smaller words indicate fewer reviews.
- Use varied, readable colors for visual distinction. **Colors must not imply positive or negative sentiment.**
- Support both single words (e.g., `parking`, `maingay`) and phrases (e.g., `water pressure`, `malapit sa`, if the phrase passes the extraction rules).
- Every displayed term should be a **tappable element**, not text baked into a static image.
- On tap, show a **bottom sheet, panel, or separate view** listing the original eligible property reviews containing that term.
- Highlight the selected word or phrase inside each displayed review while retaining the review's original wording, spelling, and language.
- Provide a clear way to close the matching-reviews view and return to the full cloud.
- Show a count such as **“Mentioned in 8 reviews”**, based on the actual number of distinct eligible reviews mentioning the term.
- Keep the layout mobile-friendly, accessible, and consistent with RentLease's existing design. Avoid excessive animation or overcrowding.

### Simplified wireframe

```text
PROPERTY DETAILS
┌─────────────────────────────────────┐
│ Property Reviews                    │
│ What renters often mention          │
│                                     │
│      parking    clean               │
│  location    WATER PRESSURE          │
│       maingay    security           │
│  ventilation    nearby stores       │
│                                     │
│ Tap a word to view related reviews  │
└─────────────────────────────────────┘

WHEN “WATER PRESSURE” IS TAPPED
┌─────────────────────────────────────┐
│ Reviews mentioning “water pressure”│
│ Mentioned in 3 reviews       [ X ]  │
│                                     │
│ “The [water pressure] is weak...”   │
│                                     │
│ “Mahina ang [water pressure] sa...”  │
│                                     │
│ “Good location, pero [water          │
│  pressure] drops at night.”         │
└─────────────────────────────────────┘
```

*Square brackets in the example above represent text highlighting, not actual characters added to reviews.*

## 3. Intended Tenant Interaction

1. The tenant opens a property's details page and navigates to **Property Reviews**.
2. The application loads the cloud for **that property only**.
3. The tenant sees commonly mentioned words/phrases sized by how many eligible reviews include them.
4. The tenant taps a term (for example, `water pressure`).
5. The app shows the **original reviews containing that term**, highlighting the matching text in each review.
6. The tenant can read the reviews, close the panel, and select another term.
7. If there are no published reviews or too few usable terms, the app displays a helpful empty or insufficient-data state rather than a misleading cloud.

## 4. Proposed NLP Approach

I propose a **lightweight, deterministic, rule-based Python NLP processor**, developed and tested independently before integration into the mobile app.

The processing pipeline should:

1. **Select eligible property reviews** for one property. Include only reviews that are published/visible and valid under the final review-visibility rules.
2. **Normalize text for matching** using Unicode normalization and case folding while preserving the original review for display.
3. **Tokenize** English, Filipino, and Taglish review text.
4. **Filter noise** such as URLs, contact information, irrelevant symbols, and configurable English/Filipino stopwords. Preserve meaningful negation (`not`, `hindi`, `walang`). Do not connect words across removed stopwords or other invalid boundaries in a way that creates misleading phrases.
5. **Automatically extract unigrams and bigrams**, without a hardcoded list of property topics. Previously unseen terms should be discoverable from reviews.
6. **Count distinct reviews per term**. Repeating `parking` several times within one review counts as **one review mention**, not multiple mentions.
7. **Associate each term with its matching review IDs** so tapping it retrieves the correct original reviews.
8. **Rank and limit terms** using configurable minimum-review frequency and maximum cloud size. Use stable, deterministic tie-breaking so the same input yields the same output.
9. **Return structured JSON** for the frontend to display; do not require the Android app to execute Python.

**Important design limits:** Do **not** use automatic sentiment analysis, positive/negative labels, AI summaries, automatic synonym merging, paid AI APIs, or model training unless a later justified requirement changes the scope. This is a **frequently mentioned terms** feature, not an accuracy claim about whether a property is good or bad.

Rule-based NLP can capture previously unseen vocabulary, but it will not always recognize that different spellings, Filipino/English expressions, or synonymous phrases have the same meaning. We can document and test this limitation rather than silently claim full semantic understanding.

## 5. Review Data and Privacy Boundaries

RentLease distinguishes between:

- **Property reviews:** tenants' experiences with a rental property. **Only these** should feed the property word cloud.
- **User reviews:** reciprocal landlord-to-tenant or tenant-to-landlord feedback. **Do not automatically mix these** into the property word cloud.

The current system uses **Supabase** for application data. Proposed `property_reviews` and `property_review_terms` storage/index structures are **not yet implemented** and should remain proposals until integration is approved.

For now, development should use **synthetic reviews** and must not modify production tables, policies, functions, records, or deployed services. For actual user data, apply authorization, review visibility, and privacy restrictions before exposing terms or matching reviews. Filtering personally identifiable text should be tested, with the understanding that rule-based filters are imperfect.

## 6. Proposed Implementation Responsibilities

| Part | Responsibility |
| --- | --- |
| **Python NLP module** | Normalize, extract terms, count distinct review mentions, and map terms to review IDs. |
| **Standalone local FastAPI API** | Expose synthetic review data and term/review responses during isolated testing. |
| **Local HTML/CSS/JavaScript viewer** | Prototype clickable cloud layout and review highlighting before mobile integration. |
| **Supabase / future secure API integration** | Store approved property-review data and serve only authorized, visible reviews and derived terms. Exact production processing architecture to be decided later. |
| **React Native frontend** | Render the final interactive cloud, handle taps, show matching reviews, and highlight the selected text. |

The final Android UI should be **native React Native**, rather than an unclickable image. The standalone browser prototype is for experimentation and verification only.

## 7. Proposed Development Order

**Phase 1 — Concept review:** Evaluate the two concept photos, refine the cloud layout, review panel, interaction flow, and mobile display requirements.

**Phase 2 — Python NLP prototype:** Build and test the rule-based English/Filipino/Taglish extraction system using synthetic property reviews.

**Phase 3 — Interactive local viewer:** Create a barebones browser word cloud with clickable terms and highlighted original matching reviews.

**Phase 4 — Validation:** Test frequency correctness, term-to-review linking, visibility filtering, privacy cases, empty data, multilingual inputs, deterministic results, and actual Android browser interaction. Do not claim Android testing has passed before it is performed.

**Phase 5 — Integration planning:** Document a JSON API contract and identify how Supabase review visibility and index updates will work.

**Phase 6 — Frontend integration:** Implement the approved UI inside the existing React Native Property Details / Property Reviews flow, without modifying unrelated features.

### Scope restrictions

- Keep initial code isolated in `Rentlease-Features/review-wordcloud/`.
- Do not modify the existing XGBoost model or Render deployment.
- Do not modify the RentLease frontend or Supabase yet.
- Do not create a new backend service solely because one exists in the prototype; choose the simplest appropriate production integration after testing.
- Keep the prototype UI barebones; polish the final UI during React Native integration.

## 8. What I Want to Discuss First

After I send the **two concept photos**, please:

1. Compare the photos with this proposed user flow and identify what should be adopted or simplified for a mobile screen.
2. Recommend the word-cloud layout and how tapping a word should open matching reviews.
3. Check that the proposed NLP approach meets our thesis scope without introducing unnecessary machine learning.
4. Identify any practical concerns with highlighting, multilingual text, long phrases, small review counts, and accessibility.
5. Provide a refined wireframe and agreed MVP behavior **before writing production code**.

**Immediate priority:** Finalize the concept, then build a working, locally testable Python processor and clickable viewer. The React Native and Supabase integrations come later.
