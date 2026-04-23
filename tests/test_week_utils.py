"""Tests for ISO-week utilities."""

from datetime import date

from src.shared.week_utils import (
    current_week,
    date_to_week,
    parse_week_arg,
    week_sunday,
    week_to_date_range,
)


class TestDateToWeek:
    def test_known_date(self):
        # 2026-04-21 is a Tuesday in W17
        assert date_to_week(date(2026, 4, 21)) == "2026-W17"

    def test_monday(self):
        assert date_to_week(date(2026, 4, 20)) == "2026-W17"

    def test_sunday(self):
        assert date_to_week(date(2026, 4, 26)) == "2026-W17"

    def test_first_week_of_year(self):
        # 2026-01-05 is Monday of W02
        assert date_to_week(date(2026, 1, 5)) == "2026-W02"

    def test_week_01(self):
        # 2025-12-29 is Monday of 2026-W01
        assert date_to_week(date(2025, 12, 29)) == "2026-W01"


class TestWeekToDateRange:
    def test_w17_2026(self):
        monday, sunday = week_to_date_range("2026-W17")
        assert monday == date(2026, 4, 20)
        assert sunday == date(2026, 4, 26)

    def test_w01_2026(self):
        monday, sunday = week_to_date_range("2026-W01")
        assert monday == date(2025, 12, 29)
        assert sunday == date(2026, 1, 4)

    def test_w53_2020(self):
        monday, sunday = week_to_date_range("2020-W53")
        assert monday == date(2020, 12, 28)
        assert sunday == date(2021, 1, 3)


class TestWeekSunday:
    def test_w17(self):
        assert week_sunday("2026-W17") == date(2026, 4, 26)


class TestParseWeekArg:
    def test_standard(self):
        assert parse_week_arg("2026-W17") == "2026-W17"

    def test_lowercase(self):
        assert parse_week_arg("2026-w17") == "2026-W17"

    def test_no_w_prefix(self):
        assert parse_week_arg("2026-17") == "2026-W17"

    def test_single_digit(self):
        assert parse_week_arg("2026-W3") == "2026-W03"

    def test_leading_spaces(self):
        assert parse_week_arg("  2026-W17  ") == "2026-W17"


class TestCurrentWeek:
    def test_returns_string(self):
        w = current_week()
        assert isinstance(w, str)
        assert "-W" in w
