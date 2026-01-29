"""UMLS concept matching using QuickUMLS.

Provides a thin wrapper around QuickUMLS with stop-word and semantic-type filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quickumls import QuickUMLS

# Common English words that happen to exist in UMLS.
STOP_WORDS: set[str] = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any",
    "are", "as", "at", "be", "been", "before", "being", "between", "both",
    "but", "by", "can", "could", "did", "do", "does", "each", "for", "from",
    "get", "had", "has", "have", "he", "her", "here", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "just", "may", "me", "might",
    "more", "most", "my", "no", "nor", "not", "now", "of", "on", "one",
    "only", "or", "other", "our", "out", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "us", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with",
    "would", "you", "your",
}  # fmt: skip

# Semantic types too abstract to be useful medical concepts.
NOISY_SEMANTIC_TYPES: set[str] = {
    "T071",  # Entity
    "T078",  # Idea or Concept
}


@dataclass
class UMLSMatch:
    """A single UMLS concept match in text."""

    start: int
    end: int
    term: str
    cui: str
    preferred_name: str
    semantic_types: list[str] = field(default_factory=list)
    similarity: float = 1.0


class Matcher:
    """UMLS concept matcher wrapping QuickUMLS."""

    def __init__(self, index_path: str = "./data/quickumls-index") -> None:
        self._matcher = QuickUMLS(index_path)

    def match_text(self, text: str) -> list[UMLSMatch]:
        """Match UMLS concepts in text, returning filtered results.

        Applies stop-word and noisy semantic-type filtering.
        Returns one match per text span (best candidate by similarity).
        """
        raw: list[list[dict[str, Any]]] = self._matcher.match(text)
        results: list[UMLSMatch] = []

        for span_matches in raw:
            if not span_matches:
                continue

            # All candidates for this span share the same text/offsets
            first = span_matches[0]
            term: str = first.get("ngram", "")

            # Skip stop words
            if term.lower() in STOP_WORDS:
                continue

            # Filter out candidates with only noisy semantic types
            good: list[dict[str, Any]] = []
            for candidate in span_matches:
                sem_types: set[str] = candidate.get("semtypes", set())
                if not sem_types or not sem_types.issubset(NOISY_SEMANTIC_TYPES):
                    good.append(candidate)

            if not good:
                continue

            # Pick best candidate by similarity score
            best = max(good, key=lambda c: c.get("similarity", 0.0))

            results.append(
                UMLSMatch(
                    start=best.get("start", 0),
                    end=best.get("end", 0),
                    term=best.get("ngram", ""),
                    cui=best.get("cui", ""),
                    preferred_name=best.get("preferred", ""),
                    semantic_types=sorted(best.get("semtypes", set())),
                    similarity=best.get("similarity", 0.0),
                )
            )

        return results
