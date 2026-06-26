from datetime import UTC, datetime, timedelta

import pytest

from app.services.momentum import is_stale, score_momentum

_NOW = datetime(2026, 6, 25, tzinfo=UTC)


def _ago(hours: float) -> datetime:
    return _NOW - timedelta(hours=hours)


def test_score_is_zero_for_no_arrivals() -> None:
    assert score_momentum([], _NOW) == 0.0


def test_fresh_member_weighs_one() -> None:
    assert score_momentum([_NOW], _NOW, momentum_half_life_hours=24.0) == 1.0


def test_member_at_one_half_life_weighs_half() -> None:
    assert score_momentum([_ago(24)], _NOW, momentum_half_life_hours=24.0) == pytest.approx(0.5)


def test_sum_rewards_accumulation_not_just_recency() -> None:
    three_fresh = score_momentum([_NOW, _NOW, _NOW], _NOW)
    one_stale = score_momentum([_ago(48)], _NOW)
    assert three_fresh > one_stale


def test_more_fresh_members_score_higher() -> None:
    # Sum keeps the member count; a mean would collapse both to ~1.0.
    assert score_momentum([_NOW] * 10, _NOW) > score_momentum([_NOW] * 3, _NOW)


def test_is_stale_when_newest_past_threshold() -> None:
    assert is_stale([_ago(49)], _NOW, momentum_stale_hours=48) is True


def test_is_active_when_any_member_is_recent() -> None:
    assert is_stale([_ago(49), _ago(2)], _NOW, momentum_stale_hours=48) is False


def test_is_stale_when_no_members() -> None:
    assert is_stale([], _NOW, momentum_stale_hours=48) is True
