"""Tests for the PR review script's helper functions."""

from scripts.analyze_pr import (
    COMMENT_MARKER,
    build_comment,
    find_existing_comment,
    truncate_diff,
)


def test_short_diff_is_not_truncated():
    diff, truncated = truncate_diff("small diff", limit=100)
    assert diff == "small diff"
    assert truncated is False


def test_long_diff_is_truncated():
    diff, truncated = truncate_diff("x" * 150, limit=100)
    assert len(diff) == 100
    assert truncated is True


def test_comment_contains_marker_and_truncation_note():
    body = build_comment("Looks good.", truncated=True)
    assert body.startswith(COMMENT_MARKER)
    assert "shortened" in body


def test_finds_earlier_bot_comment():
    comments = [
        {"id": 1, "body": "Nice work!"},
        {"id": 2, "body": f"{COMMENT_MARKER}\n## AI review\n\nOld review"},
    ]
    assert find_existing_comment(comments) == 2


def test_no_earlier_bot_comment():
    assert find_existing_comment([{"id": 1, "body": "Nice work!"}]) is None
