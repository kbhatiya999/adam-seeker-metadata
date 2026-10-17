"""Keyword search (BM25) over passages in any of the scripts the transcripts use."""

import math
import re
from collections import Counter
from typing import Dict, List, Sequence, Tuple

from seeker_sdk_knowledge import Passage

# Latin, Arabic/Urdu, Devanagari and Bengali letters including their vowel signs, plus digits. Python's \w alone
# would cut Devanagari words apart at vowel signs.
_TOKEN = re.compile(r"[0-9a-zÀ-ɏ؀-ۿऀ-ॿঀ-৿]+")
_STOP = set("""a an and are as at be but by did do does for from had has have he her his how i if in is it its me
my no not of on or our she so than that the their them then there these they this to was we were what when where
which who why will with would you your about said say says ka ki ke hai hain kya mein me ne se ko aur bhi to ye
wo jo is us kis kaun kahan the
है हैं के की का को में से ने और भी तो ये वो यह वह कि जो नहीं एक हम आप मैं था थी थे पर ही""".split())


def tokens(text: str) -> List[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and (len(t) > 1 or t.isdigit())]


class Retriever:
    """BM25 over a fixed list of passages; build once, search many times."""

    def __init__(self, passages: Sequence[Passage], k1: float = 1.5, b: float = 0.75):
        self.passages = list(passages)
        self.k1, self.b = k1, b
        self.docs = [Counter(tokens(p.text)) for p in self.passages]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf: Dict[str, float] = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> List[float]:
        q = tokens(query)
        out = []
        for d, length in zip(self.docs, self.lengths):
            s = 0.0
            for t in q:
                f = d.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * length / (self.avg or 1)))
            out.append(s)
        return out

    def search(self, query: str, k: int) -> List[Passage]:
        ranked = sorted(((s, i) for i, s in enumerate(self.scores(query)) if s > 0), key=lambda x: -x[0])
        return [self.passages[i] for _, i in ranked[:k]]

    def search_many(self, queries: Sequence[str], k: int, depth: int = 50) -> List[Passage]:
        """Several queries fused by reciprocal rank: a passage ranked high by any query comes first."""
        fused: Dict[int, float] = {}
        for query in queries:
            ranked = sorted(((s, i) for i, s in enumerate(self.scores(query)) if s > 0), key=lambda x: -x[0])
            for rank, (_, i) in enumerate(ranked[:depth]):
                fused[i] = fused.get(i, 0.0) + 1.0 / (60 + rank)
        best: List[Tuple[float, int]] = sorted(((s, i) for i, s in fused.items()), key=lambda x: -x[0])
        return [self.passages[i] for _, i in best[:k]]
