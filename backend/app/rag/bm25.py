"""In-memory BM25 keyword index (Okapi BM25 scoring with Lucene's always-positive IDF)."""
import math
import re
from collections import Counter, defaultdict

from py_rust_stemmers import SnowballStemmer

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STEMMER = SnowballStemmer("english")
STOPWORDS = frozenset(
    "a an and are as at be but by for from has have he her his i if in into is it its me my no not of on or "
    "our she so than that the their them then there these they this to was we were what when where which who "
    "why will with you your do does did can could should would about how".split()
)


def tokenize(text: str, stem: bool = True) -> list[str]:
    tokens = [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]
    return [_STEMMER.stem_word(t) for t in tokens] if stem else tokens


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75, stem: bool = True) -> None:
        self.k1, self.b, self.stem = k1, b, stem
        self.build([])

    def build(self, texts: list[str]) -> None:
        self.n_docs = len(texts)
        self.doc_len: list[int] = []
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)  # term -> [(doc_idx, term_freq)]
        for idx, text in enumerate(texts):
            tokens = tokenize(text, self.stem)
            self.doc_len.append(len(tokens))
            for term, tf in Counter(tokens).items():
                self.postings[term].append((idx, tf))
        self.avg_len = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0

    def idf(self, term: str) -> float:
        df = len(self.postings.get(term, ()))
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """Returns (doc_idx, score) pairs for documents containing at least one query term."""
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query, self.stem)):
            idf = self.idf(term)
            for idx, tf in self.postings.get(term, ()):
                norm = 1 - self.b + self.b * self.doc_len[idx] / (self.avg_len or 1)
                scores[idx] += idf * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
