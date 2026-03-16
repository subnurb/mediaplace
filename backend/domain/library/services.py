"""Pure domain services for the Library bounded context.

Track grouping, normalization, and cross-platform merging rules.
All functions are free of I/O.
"""

import re
import unicodedata


_YT_SUFFIX_RE = re.compile(
    r'\s*[-–]\s*(?:topic|official|music|vevo|records|tv|channel|hd|4k|'
    r'worldwide|audio|video|lyrics|presents)\s*$',
    re.I,
)

_ARTIST_TITLE_RE = re.compile(r'^(.{2,60}?)\s*[-–]\s*(.{2,}.*)$')


def norm_text(s):
    """Base normalization: accents, parentheticals, lowercase, word-chars only."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_artist(artist):
    """Normalize artist name, stripping YouTube channel suffixes."""
    if not artist:
        return ""
    artist = _YT_SUFFIX_RE.sub("", artist).strip()
    return norm_text(artist)


def title_candidates(raw_title):
    """Return normalized title variants.

    If the raw title looks like 'Artist - Song', also returns just the
    song portion so cross-platform grouping works when only one platform
    embeds the artist in the title.
    """
    full = norm_text(raw_title)
    candidates = [full]
    m = _ARTIST_TITLE_RE.match(raw_title.strip())
    if m:
        song_only = norm_text(m.group(2).strip())
        if song_only and song_only != full:
            candidates.append(song_only)
    return candidates


def group_key_variants(title, artist):
    """All (title_key, artist_key) candidates for cross-platform grouping.

    Returns most-specific first: (cleaned_title, artist), then title-only
    fallbacks for matching groups that lack artist info.
    """
    na = norm_artist(artist)
    t_cands = title_candidates(title)

    keys = []
    for tc in t_cands:
        if not tc:
            continue
        if na:
            keys.append((tc, na))

    for tc in t_cands:
        if tc:
            keys.append((tc, ""))

    return keys


def should_merge_groups(group_a_platforms, group_b_platforms):
    """Two groups should merge only if their platform sets are disjoint.

    Same-platform groups are never merged (they represent distinct tracks
    on the same service).
    """
    return group_a_platforms.isdisjoint(group_b_platforms)


def pick_best_field(current, candidate):
    """Pick the longer non-empty string between current and candidate."""
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if len(candidate) > len(current) else current
