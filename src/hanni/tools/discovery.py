"""Local metadata retrieval, not an intent router or execution authority.

BM25 weights uncommon terms, while bounded vocabulary correction recovers typos.
No query labels, provider downloads, phrase maps, or capability handlers occur here.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re


# Function words and conversational framing are not evidence of an operation.
# Apply this symmetrically to queries and metadata: a rare wording choice in one
# alias must not outweigh the requested object or widen a resolved read menu.
_STOP = frozenset(
    'a an the my me you it in into of to and then that this for with please hanni '
    'is are can could would should do does what which who how i we all on at right '
    'now be been have has there some any most only give show tell check get need '
    'want s as by from did why where when these those our your their them each up '
    'down out off so much many one use using used currently present inside under '
    'beneath about without both either neither other another such same own '
    'every everybody everyone everything anybody anyone anything nobody nothing '
    'none several few less more very also too just still yet already even '
    'say says said saying ask asks asked asking'.split()
)

# Absolute and explicitly relative paths are argument data. Their directory or
# basename words must not turn a file request into a model/system diagnostic.
# Keep the original utterance elsewhere for exact argument resolution.
_PATH = re.compile(
    r'(?<![\w:/\\])(?:"(?:[a-z]:[\\/]|\\\\|/|\.{1,2}[\\/])[^"\r\n]+"'
    r"|'(?:[a-z]:[\\/]|\\\\|/|\.{1,2}[\\/])[^'\r\n]+'"
    r'|(?:[a-z]:[\\/]|\\\\|/|\.{1,2}[\\/])[^\s,;!?"\']+)', re.I
)


def intent_text(text: str) -> str:
    """Normalize argument-shaped data without inspecting or rewriting files."""
    return _PATH.sub('file path', text)


def tokens(text: str) -> tuple[str, ...]:
    def singular(word):
        if len(word) > 5 and word.endswith('ies'):
            return word[:-3] + 'y'
        if len(word) > 5 and word.endswith(('sses', 'ches', 'shes', 'xes', 'zes')):
            return word[:-2]
        if len(word) > 3 and word.endswith('s') and not word.endswith(('ss', 'us')):
            return word[:-1]
        return word

    return tuple(
        singular(word) for word in re.findall(r'[a-z0-9]+', text.casefold())
        if word not in _STOP
    )


def _distance(a, b):
    """Bounded optimal-string-alignment distance, including transpositions."""
    previous_previous = None
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        row = [i]
        for j, y in enumerate(b, 1):
            value = min(row[-1] + 1, previous[j] + 1, previous[j - 1] + (x != y))
            if (previous_previous is not None and i > 1 and j > 1
                    and x == b[j - 2] and a[i - 2] == y):
                value = min(value, previous_previous[j - 2] + 1)
            row.append(value)
        if min(row) > 2:
            return 3
        previous_previous, previous = previous, row
    return previous[-1]


@dataclass(frozen=True, slots=True)
class RetrievalEvidence:
    name: str
    score: float
    coverage: float
    matched_terms: tuple[str, ...]
    corrections: tuple[tuple[str, str], ...] = ()


class HybridCapabilityIndex:
    """A revision-scoped index built solely from current registered definitions."""

    def __init__(self, catalog, *, correction_words=()):
        self.entries = {}
        self.postings = {}
        for cap in catalog:
            properties = cap.argument_schema.get('properties', {})
            argument_text = ' '.join(
                str(rule.get('description', ''))
                for rule in properties.values() if isinstance(rule, dict)
            )
            # Bound untrusted external metadata and repetition; it cannot turn
            # instructions into ranking policy or arbitrarily increase scores.
            fields = (
                (cap.name.replace('.', ' ').replace('_', ' '), 3.0),
                (' '.join(cap.tags + cap.aliases), 1.5),
                (cap.description, 1.0),
                (cap.display_name, 1.0),
                (' '.join(cap.categories), 0.5),
                (' '.join(properties) + ' ' + argument_text, 0.5),
            )
            counter = Counter()
            for text, weight in fields:
                for word, frequency in Counter(tokens(text[:8192])[:512]).items():
                    counter[word] += weight * min(frequency, 2)
            self.entries[cap.name] = counter
            for word in counter:
                self.postings.setdefault(word, set()).add(cap.name)
        n = len(self.entries)
        self.idf = {
            word: math.log(1 + (n - len(names) + 0.5) / (len(names) + 0.5))
            for word, names in self.postings.items()
        }
        self.lengths = {name: sum(counter.values()) for name, counter in self.entries.items()}
        self.mean_length = sum(self.lengths.values()) / max(1, n)
        self.vocabulary = {}
        self.correction_words = frozenset(self.postings) | frozenset(
            word for word in correction_words if isinstance(word, str) and re.fullmatch(r'[a-z]{5,32}', word))
        for word in sorted(self.correction_words):
            self.vocabulary.setdefault(len(word), []).append(word)
        self.correction_cache = {}

    def _correct(self, word):
        if word in self.correction_words or len(word) < 5:
            return word
        if word in self.correction_cache:
            return self.correction_cache[word]
        choices = []
        for length in range(len(word) - 1, len(word) + 2):
            for candidate in self.vocabulary.get(length, ()):
                # At most one substitution/insertion/deletion or transposition
                # for normal words. Longer words tolerate two edits only at a
                # high similarity; ambiguous corrections are withheld.
                if len(set(word) & set(candidate)) < max(3, len(set(word)) - 2):
                    continue
                distance = _distance(word, candidate)
                if distance <= 1 or len(word) >= 9 and distance <= 2:
                    choices.append((1 - distance / max(len(word), len(candidate)), candidate))
        choices.sort(key=lambda pair: (-pair[0], pair[1]))
        unambiguous = choices and (len(choices) == 1 or choices[0][0] - choices[1][0] >= 0.035)
        best = choices[0][1] if unambiguous else word
        if len(self.correction_cache) >= 512:
            self.correction_cache.clear()
        self.correction_cache[word] = best
        return best

    def rank(self, query: str, *, eligible=None, limit=32):
        if not 1 <= limit <= 32:
            raise ValueError('retrieval limit must be 1..32')
        original = set(tokens(query[:8192])[:128])
        corrected = {word: self._correct(word) for word in original}
        terms = set(corrected.values())
        admissible = set(self.entries) if eligible is None else set(eligible) & self.entries.keys()
        candidates = set().union(*(self.postings.get(word, set()) for word in terms)) & admissible
        unknown_idf = max(self.idf.values(), default=1)
        total_weight = sum(self.idf.get(word, unknown_idf) for word in terms)
        rows = []
        for name in candidates:
            counter = self.entries[name]
            matched = terms & counter.keys()
            length_factor = 0.25 + 0.75 * self.lengths[name] / max(1, self.mean_length)
            score = sum(
                self.idf[word] * counter[word] * 2.2 / (counter[word] + 1.2 * length_factor)
                for word in matched
            )
            coverage = sum(self.idf[word] for word in matched) / max(total_weight, 1e-9)
            corrections = tuple(sorted((a, b) for a, b in corrected.items() if a != b and b in matched))
            rows.append(RetrievalEvidence(name, score, coverage, tuple(sorted(matched)), corrections))
        return tuple(sorted(rows, key=lambda row: (-row.score, row.name))[:limit])

    def candidates(self, query: str, *, eligible=None, ceiling=8):
        rows = self.rank(query, eligible=eligible)
        if not rows:
            return ()
        top = rows[0]
        # Two distinct metadata terms avoid exposing tools because of a lone
        # conversational word. These are evidence scores, not probabilities.
        supported = [
            row for row in rows if len(row.matched_terms) >= 2 and row.coverage >= 0.20
            and row.score >= max(2.5, top.score * 0.55)
        ]
        if not supported:
            return ()
        # A clear winner needs less context; close scores preserve alternatives.
        if len(supported) > 1 and supported[0].score >= supported[1].score * 1.8:
            supported = supported[:1]
        return tuple(supported[:max(1, min(8, ceiling))])


def index_for(registry):
    from hanni.tools.capabilities import describe
    from dataclasses import replace
    cached = getattr(registry, '_retrieval_v2_cache', None)
    if cached is not None and cached[0] == registry.revision:
        return cached[1]
    revision = registry.revision
    # Legacy curated retrieval hints remain in the original ranker. This
    # statistical index uses the actual definition's aliases, not appended
    # phrase-derived hints, so a broad legacy hint cannot become new evidence.
    from hanni.tools.intent_prototypes import _ALIASES
    index = HybridCapabilityIndex(tuple(
        replace(describe(definition), aliases=definition.aliases)
        for definition in registry.definitions()
    ), correction_words=_ALIASES.keys())
    # A concurrent mutation must not publish a stale index as current.
    if registry.revision == revision:
        registry._retrieval_v2_cache = (revision, index)
    return index
