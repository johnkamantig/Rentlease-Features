"""Deterministic lexical extraction; offsets are end-exclusive Unicode code points."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import unicodedata


COLORS = ("blue", "green", "orange", "purple", "pink")
NEGATIONS = {"not", "no", "never", "hindi", "walang", "wala", "di"}
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

    def occurrences(self, text):
        """Tokenize original Unicode letters/marks; normalize only separate token values.

        Removed tokens reset adjacency. Only horizontal whitespace joins a bigram.
        Keeping original token boundaries avoids offset drift from NFKC/casefold.
        """
        blocked = [(m.start(), m.end()) for m in NOISE.finditer(text)]
        previous = None
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
            # Discard letter fragments adjacent to digits/underscores, e.g. unit123.
            invalid_edge = ((start > 0 and (text[start - 1].isdigit() or text[start - 1] == "_"))
                            or (end < len(text) and (text[end].isdigit() or text[end] == "_")))
            if (word in self.stopwords or len(word) < 2 or invalid_edge
                    or any(start < b and end > a for a, b in blocked)):
                previous = None
                continue
            yield word, start, end
            if previous:
                prev_word, prev_start, prev_end = previous
                gap = text[prev_end:start]
                if gap and all(c.isspace() and c not in "\r\n\u2028\u2029" for c in gap):
                    yield prev_word + " " + word, prev_start, end
            previous = (word, start, end)

    def _index(self, property_id, reviews):
        rows = eligible(property_id, reviews)
        index = {}
        usable = 0
        for row in rows:
            found = False
            for term, start, end in self.occurrences(row["text"]):
                found = True
                index.setdefault(term, {}).setdefault(row["id"], []).append({"start": start, "end": end})
            usable += int(found)
        return rows, index, usable

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
