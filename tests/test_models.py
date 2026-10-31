from datetime import datetime, timedelta, timezone

import pytest

from trustnet.models import Decision, Network, Project, parse_time


def test_parse_time_accepts_z_offset_and_datetime():
    expected = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
    assert parse_time("2026-10-31T12:00:00Z") == expected
    assert parse_time("2026-10-31T12:00:00+00:00") == expected
    assert parse_time(expected) == expected


def test_parse_time_converts_other_offsets_to_utc():
    assert parse_time("2026-10-31T17:30:00+05:30") == datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
    ist = timezone(timedelta(hours=5, minutes=30))
    assert parse_time(datetime(2026, 10, 31, 17, 30, tzinfo=ist)) == datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


def test_parse_time_treats_naive_as_utc():
    assert parse_time("2026-10-31T12:00:00") == datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("bad", ["yesterday", "", None, 5])
def test_parse_time_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_time(bad)


def test_list_fields_are_not_shared_between_instances():
    a, b = Project(id="a", name="a"), Project(id="b", name="b")
    a.vouches.append("x")
    assert b.vouches == []
    assert Network().projects is not Network().projects
    assert Decision("pr", "v", "h", "ACCEPT", 0.8, 0.0, 0.2).reasons == []
