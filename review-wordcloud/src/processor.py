"""Deterministic lexical extraction; offsets are end-exclusive Unicode code points.

Term counting uses scikit-learn's CountVectorizer (unigrams + bigrams, binary=True), so a
term's count is the number of reviews that contain it (document frequency, no IDF).
CountVectorizer returns no positions, so ``_spans`` locates each selected term in the
original review text with the same scanner that feeds the vectorizer.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from sklearn.feature_extraction.text import CountVectorizer


COLORS = ("blue", "green", "orange", "purple", "pink")
NEGATIONS = {"not", "no", "never", "hindi", "walang", "wala", "di"}
# Marks a hard boundary (punctuation, newline, noise, rejected fragment). It can never be
# part of a letters-only token, so n-grams containing it are discarded after vectorizing.
BREAK = "|"
NOISE = re.compile(
    r"(?:https?://|www\.)[^\s<>]+|"
    r"[\w.+-]+@[\w.-]+\.[\w-]+|"
    r"(?<!\w)(?:\+?\d[\d ()\-–.]{5,}\d)(?!\w)|"
    r"(?<!\w)@[\w]+", re.IGNORECASE)


def normalize(text):
    return unicodedata.normalize("NFKC", text).casefold()


@dataclass(frozen=True)
class Config:
    min_reviews: int = 2
    min_usable_reviews: int = 2
    max_terms: int = 24

    def __post_init__(self):
        if min(self.min_reviews, self.min_usable_reviews, self.max_terms) < 1:
            raise ValueError("Thresholds must be positive")


def eligible(property_id, reviews):
    """Fail closed on missing flags. This is fixture policy, not authorization."""
    result = []
    seen = set()
    for r in reviews:
        if not (r.get("property_id") == property_id and r.get("kind") == "property"
                and r.get("published") is True and r.get("visible") is True
                and r.get("moderation_status") == "approved"
                and isinstance(r.get("text"), str) and r["text"].strip()):
            continue
        if not isinstance(r.get("id"), str) or not r["id"] or r["id"] in seen:
            raise ValueError("Eligible reviews require unique nonempty string IDs")
        seen.add(r["id"])
        result.append(r)
    return sorted(result, key=lambda r: r["id"])


class Processor:
    def __init__(self, config=None, stopwords=None):
        self.config = config or Config()
        if stopwords is None:
            groups = json.loads(Path(__file__).with_name("stopwords.json").read_text(encoding="utf-8"))
            stopwords = {word for group in groups.values() for word in group}
        self.stopwords = {normalize(w) for w in stopwords} - NEGATIONS
        # Only stopwords the tokenizer can actually produce are handed to CountVectorizer
        # (one-letter words and the like are already rejected by the scanner).
        self._stop = frozenset(w for w in self.stopwords if self._preprocess(w) == w)

    @staticmethod
    def _scan(text):
        """Tokenize original Unicode letters/marks. Returns ``(word, start, end)`` items, with
        ``None`` as a hard boundary.

        Token values are normalized (NFKC + casefold) one by one while offsets stay on the
        original text, so offsets never drift. Noise (URLs, e-mails, phone numbers, @mentions),
        letter fragments touching digits/underscores, and one-letter words become boundaries.
        Tokens separated by anything other than horizontal whitespace are also separated by a
        boundary, so n-grams never cross punctuation or line breaks.
        """
        blocked = [(m.start(), m.end()) for m in NOISE.finditer(text)]
        items = []
        previous_end = None
        index = 0
        while index < len(text):
            if not unicodedata.category(text[index]).startswith("L"):
                index += 1
                continue
            start = index
            index += 1
            while index < len(text) and unicodedata.category(text[index])[0] in "LM":
                index += 1
            end = index
            word = normalize(text[start:end])
            invalid_edge = ((start > 0 and (text[start - 1].isdigit() or text[start - 1] == "_"))
                            or (end < len(text) and (text[end].isdigit() or text[end] == "_")))
            if (len(word) < 2 or invalid_edge or any(c.isspace() or c == BREAK for c in word)
                    or any(start < b and end > a for a, b in blocked)):
                items.append(None)
                previous_end = None
                continue
            if previous_end is not None:
                gap = text[previous_end:start]
                if not all(c.isspace() and c not in "\r\n  " for c in gap):
                    items.append(None)
            items.append((word, start, end))
            previous_end = end
        return items

    @classmethod
    def _preprocess(cls, text):
        """CountVectorizer preprocessor: noise removal + NFKC/casefold, one space between tokens."""
        return " ".join(BREAK if item is None else item[0] for item in cls._scan(text))

    def _vectorizer(self, min_df):
        return CountVectorizer(
            preprocessor=self._preprocess,
            lowercase=False,          # normalization is done by the preprocessor
            token_pattern=r"\S+",     # preprocessor already isolates letter/mark tokens
            stop_words=sorted(self._stop),
            ngram_range=(1, 2),
            binary=True,              # each term counts once per review
            min_df=min_df,
            dtype=int)

    def _spans(self, text, terms):
        """Locate selected terms in the original text; same rules as the vectorizer.

        Stopwords are dropped (without a boundary) before bigrams are formed, so a bigram
        whose words were joined across removed stopwords spans first word start to second
        word end.
        """
        kept = [item for item in self._scan(text) if item is None or item[0] not in self._stop]
        found = {}
        for position, item in enumerate(kept):
            if item is None:
                continue
            word, start, end = item
            if word in terms:
                found.setdefault(word, []).append({"start": start, "end": end})
            following = kept[position + 1] if position + 1 < len(kept) else None
            if following is not None:
                term = word + " " + following[0]
                if term in terms:
                    found.setdefault(term, []).append({"start": start, "end": following[2]})
        return found

    def _index(self, property_id, reviews):
        rows = eligible(property_id, reviews)
        usable = sum(any(item is not None and item[0] not in self._stop for item in self._scan(r["text"]))
                     for r in rows)
        min_df = self.config.min_reviews
        if len(rows) < min_df:
            return rows, {}, usable
        try:
            vectorizer = self._vectorizer(min_df)
            matrix = vectorizer.fit_transform([r["text"] for r in rows])
        except ValueError:  # "empty vocabulary" / "no terms remain after pruning"
            return rows, {}, usable
        frequency = matrix.sum(axis=0).A1  # binary matrix: column sum = number of reviews
        counts = {name: int(frequency[i]) for i, name in enumerate(vectorizer.get_feature_names_out())
                  if BREAK not in name}
        index = {}
        for row in rows:
            for term, spans in self._spans(row["text"], counts).items():
                index.setdefault(term, {})[row["id"]] = spans
        # CountVectorizer's document frequency is authoritative; drop a term if the span
        # finder ever disagrees rather than show a count that does not match its highlights.
        return rows, {t: m for t, m in index.items() if len(m) == counts[t]}, usable

    @staticmethod
    def metadata(term, matches, maximum):
        digest = hashlib.sha256(term.encode("utf-8")).hexdigest()
        return {"id": "t-" + digest, "text": term, "review_count": len(matches),
                "review_ids": sorted(matches), "color": COLORS[int(digest[:8], 16) % len(COLORS)],
                "font_size_rem": round(1 + 1.3 * len(matches) / maximum, 3)}

    def cloud(self, property_id, reviews):
        rows, index, usable = self._index(property_id, reviews)
        ranked = sorted((t for t in index if len(index[t]) >= self.config.min_reviews),
                        key=lambda t: (-len(index[t]), t))
        status = "empty" if not rows else "insufficient_data"
        terms = []
        if usable >= self.config.min_usable_reviews and ranked:
            status = "ready"
            maximum = len(index[ranked[0]])
            terms = [self.metadata(t, index[t], maximum) for t in ranked[:self.config.max_terms]]
        return {"property_id": property_id, "status": status, "synthetic": True,
                "eligible_review_count": len(rows), "usable_review_count": usable,
                "thresholds": {"min_review_mentions": self.config.min_reviews,
                               "min_usable_reviews": self.config.min_usable_reviews},
                "span_encoding": "unicode_code_points", "terms": terms,
                "reviews": [{"id": r["id"], "text": r["text"]} for r in rows]}

    def matching(self, property_id, term_id, reviews):
        cloud = self.cloud(property_id, reviews)
        term = next((t for t in cloud["terms"] if t["id"] == term_id), None)
        if term is None:
            raise KeyError(term_id)
        rows, index, _ = self._index(property_id, reviews)
        matches = index[term["text"]]
        return {"property_id": property_id, "term": term,
                "span_encoding": "unicode_code_points", "synthetic": True,
                "reviews": [{"id": r["id"], "text": r["text"], "spans": matches[r["id"]]}
                            for r in rows if r["id"] in matches]}
