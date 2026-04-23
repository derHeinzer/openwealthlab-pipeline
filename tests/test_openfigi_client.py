"""Tests for OpenFIGI client helpers."""

from src.shared.openfigi_client import _pick_best


class TestPickBest:
    def test_prefers_equity_with_composite(self):
        matches = [
            {"marketSector": "Govt", "ticker": "T"},
            {"marketSector": "Equity", "compositeFIGI": "BBG123", "ticker": "AAPL"},
            {"marketSector": "Equity", "ticker": "AAPL2"},
        ]
        assert _pick_best(matches)["ticker"] == "AAPL"

    def test_prefers_equity_over_other(self):
        matches = [
            {"marketSector": "Govt", "ticker": "T"},
            {"marketSector": "Equity", "ticker": "AAPL"},
        ]
        assert _pick_best(matches)["ticker"] == "AAPL"

    def test_fallback_to_first(self):
        matches = [
            {"marketSector": "Govt", "ticker": "T"},
        ]
        assert _pick_best(matches)["ticker"] == "T"

    def test_empty_returns_none(self):
        assert _pick_best([]) is None
