import unittest

from src.processor import Processor, Config


def review(id, text, **extra):
    return dict(id=id, property_id="p", text=text, published=True,
                visible=True, moderation_status="approved", kind="property", **extra)


class ProcessorTests(unittest.TestCase):
    def setUp(self):
        self.processor = Processor(Config(min_reviews=1, min_usable_reviews=1))

    def terms(self, rows):
        return {t["text"]: t for t in self.processor.cloud("p", rows)["terms"]}

    def test_multilingual_unseen_and_distinct_mentions(self):
        terms = self.terms([review("1", "Clean clean MALINIS parking area"),
                            review("2", "Malinis ang unit and parking area; presko")])
        self.assertEqual(terms["clean"]["review_count"], 1)
        self.assertEqual(terms["malinis"]["review_count"], 2)
        self.assertEqual(terms["parking area"]["review_ids"], ["1", "2"])
        self.assertIn("presko", terms)

    def test_boundaries_and_contact_noise(self):
        terms = self.terms([review("1", "clean ang unit. parking https://example.test/contact area; bright name@example.test room; quiet 0917-123-4567 hall; airy, balcony; safe\nentrance")])
        for forbidden in ["clean unit", "unit parking", "parking area", "bright room", "quiet hall", "airy balcony", "safe entrance", "example", "contact"]:
            self.assertNotIn(forbidden, terms)

    def test_unicode_original_spans_and_no_substrings(self):
        text = "🏠 ＣＬＥＡＮ, clean! cleaning; Cafe\u0301 café; Water\tPRESSURE"
        rows = [review("1", text)]
        terms = self.terms(rows)
        result = self.processor.matching("p", terms["clean"]["id"], rows)
        spans = result["reviews"][0]["spans"]
        self.assertEqual([text[s["start"]:s["end"]] for s in spans], ["ＣＬＥＡＮ", "clean"])
        cafe = self.processor.matching("p", terms["café"]["id"], rows)
        self.assertEqual(len(cafe["reviews"][0]["spans"]), 2)
        phrase = self.processor.matching("p", terms["water pressure"]["id"], rows)
        s = phrase["reviews"][0]["spans"][0]
        self.assertEqual(text[s["start"]:s["end"]], "Water\tPRESSURE")

    def test_negations_and_custom_stopwords(self):
        processor = Processor(Config(min_reviews=1, min_usable_reviews=1), stopwords={"not", "hindi", "walang", "unit"})
        terms = {t["text"] for t in processor.cloud("p", [review("1", "not clean hindi tahimik walang parking unit")])["terms"]}
        self.assertTrue({"not clean", "hindi tahimik", "walang parking"} <= terms)
        self.assertNotIn("unit", terms)

    def test_eligibility_and_property_scope(self):
        rows = [review("ok", "parking")]
        for key, value in [("visible", False), ("published", False), ("moderation_status", "pending"), ("moderation_status", "moderated"), ("kind", "user"), ("property_id", "other")]:
            row = review(str(len(rows)), "secret parking")
            row[key] = value
            rows.append(row)
        row = review("missing", "secret")
        del row["published"]
        rows.append(row)
        terms = self.terms(rows)
        self.assertNotIn("secret", terms)
        self.assertEqual(terms["parking"]["review_ids"], ["ok"])

    def test_determinism_sorting_color_and_linking(self):
        rows = [review("b", "parking clean"), review("a", "parking malinis")]
        first = self.processor.cloud("p", rows)
        self.assertEqual(first, self.processor.cloud("p", rows[::-1]))
        self.assertEqual(first["terms"][0]["text"], "parking")
        for term in first["terms"]:
            linked = self.processor.matching("p", term["id"], rows)
            self.assertEqual(term["review_ids"], [r["id"] for r in linked["reviews"]])
        with self.assertRaises(KeyError):
            self.processor.matching("other", first["terms"][0]["id"], rows)

    def test_empty_insufficient_and_duplicate_ids(self):
        processor = Processor()
        self.assertEqual(processor.cloud("p", []) ["status"], "empty")
        self.assertEqual(processor.cloud("p", [review("1", "parking")])["status"], "insufficient_data")
        self.assertEqual(processor.cloud("p", [review("1", "ang the")])["terms"], [])
        self.assertEqual(processor.cloud("unknown", [review("1", "parking")])["terms"], [])
        with self.assertRaises(ValueError):
            processor.cloud("p", [review("1", "parking"), review("1", "clean")])


if __name__ == "__main__":
    unittest.main()
