import json
from pathlib import Path
import unittest

from sklearn.feature_extraction.text import CountVectorizer

from src.processor import Processor
from tests.legacy_processor import Processor as LegacyProcessor

FIXTURES = json.loads((Path(__file__).parents[1] / "fixtures" / "reviews.json").read_text(encoding="utf-8"))


def review(id, text, property_id="p"):
    return dict(id=id, property_id=property_id, text=text, published=True,
                visible=True, moderation_status="approved", kind="property")


def spans_of(processor, rows, term_text, property_id="p"):
    cloud = processor.cloud(property_id, rows)
    term = next(t for t in cloud["terms"] if t["text"] == term_text)
    return processor.matching(property_id, term["id"], rows)


class CountVectorizerTests(unittest.TestCase):
    def test_uses_countvectorizer_binary_unigram_bigram_min_df(self):
        vectorizer = Processor()._vectorizer(2)
        self.assertIsInstance(vectorizer, CountVectorizer)
        self.assertEqual((vectorizer.ngram_range, vectorizer.binary, vectorizer.min_df),
                         ((1, 2), True, 2))

    def test_example_wifi_counts_and_clean_absent(self):
        rows = [review("1", "Room was very clean and Wifi was fast"), review("2", "Wifi was good")]
        cloud = Processor().cloud("p", rows)
        terms = {t["text"]: t for t in cloud["terms"]}
        self.assertEqual(terms["wifi"]["review_count"], 2)
        self.assertNotIn("clean", terms)
        self.assertEqual(cloud["status"], "ready")

    def test_repeated_word_counts_once_per_review(self):
        rows = [review("1", "wifi wifi wifi wifi"), review("2", "WIFI")]
        term = {t["text"]: t for t in Processor().cloud("p", rows)["terms"]}["wifi"]
        self.assertEqual(term["review_count"], 2)
        matches = spans_of(Processor(), rows, "wifi")["reviews"]
        self.assertEqual(len(matches[0]["spans"]), 4)  # every occurrence highlighted, counted once

    def test_filipino_stopwords_and_negations(self):
        rows = [review("1", "Ang unit ay malinis, hindi maingay"), review("2", "Hindi maingay at walang baha sa unit")]
        terms = {t["text"] for t in Processor().cloud("p", rows)["terms"]}
        for stop in ["ang", "ay", "sa", "at"]:
            self.assertNotIn(stop, terms)
        self.assertIn("hindi maingay", terms)
        self.assertNotIn("hindi", terms)  # same two reviews as "hindi maingay": phrase wins
        self.assertIn("unit", terms)
        self.assertNotIn("walang", terms)  # only in one review

    def test_single_review_terms_excluded_and_too_few_usable_reviews(self):
        rows = [review("1", "parking spacious"), review("2", "parking noisy")]
        terms = {t["text"] for t in Processor().cloud("p", rows)["terms"]}
        self.assertEqual(terms, {"parking"})
        one = Processor().cloud("p", [review("1", "parking parking")])
        self.assertEqual((one["status"], one["terms"]), ("insufficient_data", []))
        stop_only = Processor().cloud("p", [review("1", "parking"), review("2", "ang the")])
        self.assertEqual((stop_only["status"], stop_only["terms"]), ("insufficient_data", []))

    def test_bigrams_form_after_stopword_removal_but_not_across_punctuation(self):
        rows = [review("1", "room was very clean; quiet\nhall"), review("2", "Room is clean, quiet. hall")]
        terms = {t["text"] for t in Processor().cloud("p", rows)["terms"]}
        self.assertIn("room clean", terms)
        for blocked in ["clean quiet", "quiet hall"]:
            self.assertNotIn(blocked, terms)

    def test_span_roundtrip_unigrams_and_bigrams_with_emoji_and_accents(self):
        rows = [review("1", "\U0001F3E0 Room was very clean, Café au lait! \U0001F389 wifi fast"),
                review("2", "Ｒｏｏｍ  is clean; café au lait and WIFI \U0001F389 fast"),
                review("3", "\U0001F600\U0001F600 room\twas\tclean wifi fast, Café au lait")]
        processor = Processor()
        cloud = processor.cloud("p", rows)
        self.assertTrue(any(" " in t["text"] for t in cloud["terms"]))
        checked = 0
        for term in cloud["terms"]:
            result = processor.matching("p", term["id"], rows)
            self.assertEqual(term["review_count"], len(result["reviews"]))
            for entry in result["reviews"]:
                for span in entry["spans"]:
                    sliced = entry["text"][span["start"]:span["end"]]
                    words = Processor._preprocess(sliced).split()
                    # Sliced by code points, the text starts and ends with the term's words
                    # (removed stopwords may sit between the two words of a bigram).
                    self.assertEqual(words[0], term["text"].split()[0])
                    self.assertEqual(words[-1], term["text"].split()[-1])
                    if " " not in term["text"]:
                        self.assertEqual(words, [term["text"]])
                    checked += 1
        self.assertGreater(checked, 8)
        by_id = {e["id"]: e for e in spans_of(processor, rows, "room clean")["reviews"]}
        s = by_id["1"]["spans"][0]
        self.assertEqual(by_id["1"]["text"][s["start"]:s["end"]], "Room was very clean")
        s = by_id["3"]["spans"][0]
        self.assertEqual(by_id["3"]["text"][s["start"]:s["end"]], "room\twas\tclean")

    def test_spans_agree_with_document_frequency_on_fixtures(self):
        processor = Processor()
        for prop in FIXTURES["properties"]:
            cloud = processor.cloud(prop["id"], FIXTURES["reviews"])
            for term in cloud["terms"]:
                result = processor.matching(prop["id"], term["id"], FIXTURES["reviews"])
                self.assertEqual(term["review_count"], len(result["reviews"]))
                self.assertEqual(term["review_ids"], [r["id"] for r in result["reviews"]])

    def test_output_format_matches_legacy_on_fixture_corpus(self):
        new, old = Processor(), LegacyProcessor()
        for prop in FIXTURES["properties"]:
            a = new.cloud(prop["id"], FIXTURES["reviews"])
            b = old.cloud(prop["id"], FIXTURES["reviews"])
            self.assertEqual(a.keys(), b.keys())
            self.assertEqual(a["status"], b["status"])
            self.assertEqual(a["usable_review_count"], b["usable_review_count"])
            self.assertEqual(a["reviews"], b["reviews"])
            self.assertLessEqual(len(a["terms"]), 24)
            if a["terms"] and b["terms"]:
                self.assertEqual(a["terms"][0].keys(), b["terms"][0].keys())
        demo_new = new.cloud("demo", FIXTURES["reviews"])
        demo_old = old.cloud("demo", FIXTURES["reviews"])
        old_counts = {t["text"]: t["review_count"] for t in demo_old["terms"]}
        # A unigram's count is unchanged; only bigrams differ (stopword-joined pairs).
        for term in demo_new["terms"]:
            if " " not in term["text"] and term["text"] in old_counts:
                self.assertEqual(term["review_count"], old_counts[term["text"]])
        self.assertEqual(demo_new["terms"],
                         sorted(demo_new["terms"], key=lambda t: (-t["review_count"], t["text"])))

    def texts(self, rows):
        return {t["text"]: t["review_count"] for t in Processor().cloud("p", rows)["terms"]}

    def test_phrase_replaces_its_words_when_review_sets_are_identical(self):
        rows = [review("1", "Wifi fast"), review("2", "wifi fast, wifi")]
        self.assertEqual(self.texts(rows), {"wifi fast": 2})
        rows = [review("1", "fast wifi"), review("2", "Fast WiFi!")]  # word can be second
        self.assertEqual(self.texts(rows), {"fast wifi": 2})

    def test_word_kept_when_it_also_appears_in_other_reviews(self):
        rows = [review("1", "wifi fast"), review("2", "wifi fast"), review("3", "wifi good")]
        # "wifi" is in 3 reviews, the phrase in 2: both stay. "fast" matches the phrase's reviews: dropped.
        self.assertEqual(self.texts(rows), {"wifi": 3, "wifi fast": 2})

    def test_dropped_word_leaves_no_highlight_and_phrase_keeps_counts_and_spans(self):
        rows = [review("1", "Wifi was fast"), review("2", "wifi fast!")]
        processor = Processor()
        cloud = processor.cloud("p", rows)
        self.assertEqual([t["text"] for t in cloud["terms"]], ["wifi fast"])
        result = processor.matching("p", cloud["terms"][0]["id"], rows)
        self.assertEqual(cloud["terms"][0]["review_count"], len(result["reviews"]))
        by_id = {e["id"]: e for e in result["reviews"]}
        s = by_id["1"]["spans"][0]
        self.assertEqual(by_id["1"]["text"][s["start"]:s["end"]], "Wifi was fast")

    def test_freed_slots_go_to_other_terms(self):
        rows = [review("1", "wifi fast parking"), review("2", "wifi fast parking")]
        # unigrams wifi/fast/parking all share the same reviews as their phrases.
        self.assertEqual(self.texts(rows), {"wifi fast": 2, "fast parking": 2})


if __name__ == "__main__":
    unittest.main()
