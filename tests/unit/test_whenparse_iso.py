"""Exact owner-provided ISO values must not become natural-language guesses."""
from datetime import datetime, timedelta, timezone
import pytest
from hanni.tools.todos import TodoStore
from hanni.tools.whenparse import WhenParseError, parse_when

@pytest.mark.parametrize('text', ['2030-06-12T15:00:00-04:00', '2030-06-12T15:00+05:30', '2030-06-12T15:00:00Z', '2030-06-12T15:00:00.123456+00:00', '2030-06-12 15:00', '2030-06-12T15:00:59'])
def test_exact_datetime_preserves_date_time_and_explicit_offset(text):
    result = parse_when(text, now=datetime(2026, 10, 9, 17), default_minutes=30)
    assert result.start == datetime.fromisoformat(text.replace('Z', '+00:00'))
    assert result.start.isoformat() == datetime.fromisoformat(text.replace('Z', '+00:00')).isoformat()
    assert not result.all_day and result.duration_minutes == 30
    assert result.end == result.start + timedelta(minutes=30)

def test_exact_date_is_all_day_without_invented_timezone_or_current_year(tmp_path):
    result = parse_when('2030-06-12', now=datetime(2026, 10, 9))
    assert result.start == datetime(2030, 6, 12) and result.all_day
    assert result.start.tzinfo is None
    store = TodoStore(tmp_path)
    row = store.add({'title': 'Future isolated due date', 'due': '2030-06-12T15:00:00-04:00'})
    assert store.get(row['id'])['due'] == '2030-06-12T15:00:00-04:00'

@pytest.mark.parametrize('text', ['2030-02-30', '2030-02-30T15:00:00-04:00', '2030-06-12T25:00', '2030-06-12T15:60', '2030-06-12T15:00:60', '2030-06-12T15:00+04:99', '2030-06-12T15:00+24:00', '2030-06-12T15:00-0400', '2030-06-12T15:00Z trailing', '2030-06-12T', '2030-06-12 15:00+bad', '2030-6-12T15:00', '2030-6-12', '2030-06-12+05:00'])
def test_malformed_iso_does_not_fall_through_to_next_clock_occurrence(text):
    with pytest.raises(WhenParseError):
        parse_when(text, now=datetime(2026, 10, 9, 17))

def test_existing_natural_language_and_explicit_date_phrase_remain_supported():
    now = datetime(2026, 10, 9, 17)
    assert parse_when('tomorrow at 3pm', now=now).start == datetime(2026, 10, 10, 15)
    assert parse_when('2030-06-12 at 3pm', now=now).start == datetime(2030, 6, 12, 15)
    assert parse_when('2030-06-12T15:00:00Z for 30 minutes', now=now).start.tzinfo == timezone.utc
