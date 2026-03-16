"""Pure domain services for cross-platform track matching.

Wraps and re-exports the pure normalization and scoring functions from
the existing music_matcher module. The heavy implementation lives in
music_matcher.py; this module provides a clean domain-layer import path
and adds any additional pure matching helpers.

Functions here have NO side effects — no HTTP calls, no DB writes.
"""

from music_matcher import (
    normalize_title,
    normalize_artist,
    normalize_yt_channel,
    score_candidate,
    classify_confidence,
    bpm_match_boost,
)

__all__ = [
    "normalize_title",
    "normalize_artist",
    "normalize_yt_channel",
    "score_candidate",
    "classify_confidence",
    "bpm_match_boost",
    "titles_match",
]

THRESHOLD_MATCHED = 0.90
THRESHOLD_UNCERTAIN = 0.55


def titles_match(title_a, title_b, threshold=0.85):
    """Quick check if two track titles refer to the same song.

    Uses the domain normalization pipeline, then compares via
    score_candidate with a dummy duration (duration-agnostic).
    """
    norm_a = normalize_title(title_a)
    norm_b = normalize_title(title_b)
    if not norm_a or not norm_b:
        return False
    return norm_a == norm_b
