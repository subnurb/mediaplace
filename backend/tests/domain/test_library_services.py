"""Tests for domain.library.services — pure library business logic."""

from domain.library.services import (
    group_key_variants,
    norm_artist,
    norm_text,
    pick_best_field,
    should_merge_groups,
    title_candidates,
)


class TestNormText:

    def test_lowercase_and_whitespace(self):
        assert norm_text("  Hello   World  ") == "hello world"

    def test_strips_parentheticals(self):
        assert norm_text("Runaway (feat. Kanye)") == "runaway"

    def test_strips_brackets(self):
        assert norm_text("Song [Remix]") == "song"

    def test_strips_accents(self):
        assert norm_text("café") == "cafe"

    def test_empty_string(self):
        assert norm_text("") == ""

    def test_punctuation_to_space(self):
        assert norm_text("hello-world") == "hello world"


class TestNormArtist:

    def test_strips_topic_suffix(self):
        assert norm_artist("AURORA - Topic") == "aurora"

    def test_strips_vevo_suffix(self):
        assert norm_artist("DaftPunkVEVO") == "daftpunkvevo"

    def test_strips_official_suffix(self):
        assert norm_artist("Eminem – Official") == "eminem"

    def test_empty_string(self):
        assert norm_artist("") == ""


class TestTitleCandidates:

    def test_simple_title(self):
        result = title_candidates("Runaway")
        assert "runaway" in result

    def test_artist_dash_title(self):
        result = title_candidates("AURORA - Runaway")
        assert len(result) == 2
        assert "runaway" in result  # song-only variant

    def test_no_dash_single_candidate(self):
        result = title_candidates("Song Name")
        assert len(result) == 1


class TestGroupKeyVariants:

    def test_with_artist(self):
        keys = group_key_variants("Runaway", "AURORA")
        assert len(keys) >= 2
        assert ("runaway", "aurora") in keys
        assert ("runaway", "") in keys  # title-only fallback

    def test_without_artist(self):
        keys = group_key_variants("Runaway", "")
        assert len(keys) >= 1
        assert all(k[1] == "" for k in keys)

    def test_artist_title_split(self):
        keys = group_key_variants("AURORA - Runaway", "AURORA")
        normalized_titles = {k[0] for k in keys}
        assert "runaway" in normalized_titles


class TestShouldMergeGroups:

    def test_disjoint_platforms_should_merge(self):
        assert should_merge_groups({"spotify"}, {"youtube_publish"}) is True

    def test_overlapping_platforms_should_not_merge(self):
        assert should_merge_groups({"spotify", "youtube_publish"}, {"spotify"}) is False

    def test_empty_sets(self):
        assert should_merge_groups(set(), {"spotify"}) is True


class TestPickBestField:

    def test_picks_longer(self):
        assert pick_best_field("short", "much longer value") == "much longer value"

    def test_keeps_current_when_candidate_shorter(self):
        assert pick_best_field("current value", "short") == "current value"

    def test_candidate_when_current_empty(self):
        assert pick_best_field("", "value") == "value"

    def test_current_when_candidate_empty(self):
        assert pick_best_field("value", "") == "value"

    def test_both_empty(self):
        assert pick_best_field("", "") == ""
