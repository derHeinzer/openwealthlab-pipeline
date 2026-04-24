"""Tests for the portfolio markdown generator."""

import yaml

from src.portfolio.generate_markdown import generate_markdown


def _parse_frontmatter(md: str) -> dict:
    """Extract and parse YAML frontmatter from markdown."""
    parts = md.split("---", 2)
    return yaml.safe_load(parts[1])


_SAMPLE_TX = [
    {
        "date": "2026-04-21",
        "type": "buy",
        "stock": "Apple Inc.",
        "isin": "US0378331005",
        "ticker": "AAPL",
        "shares": 10,
        "price_per_share": 150.25,
        "total_amount": 1502.50,
        "currency": "EUR",
        "fees": 1.00,
        "tax_withheld": 0.50,
        "is_savings_plan": True,
        "week": "2026-W17",
        "year": 2026,
    },
    {
        "date": "2026-04-22",
        "type": "sell",
        "stock": "Tesla Inc.",
        "isin": "US88160R1014",
        "ticker": "TSLA",
        "shares": 5,
        "price_per_share": 200.00,
        "total_amount": 1000.00,
        "currency": "EUR",
        "fees": 1.00,
        "tax_withheld": 3.25,
        "is_savings_plan": False,
        "week": "2026-W17",
        "year": 2026,
    },
]


class TestGeneratePortfolioMarkdown:
    def test_contains_frontmatter(self):
        md = generate_markdown("2026-W17")
        assert "---" in md
        fm = _parse_frontmatter(md)
        assert fm["type"] == "portfolio-log"
        assert fm["week"] == "2026-W17"

    def test_title(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17"))
        assert fm["title"] == "Portfolio Log – Week 17, 2026"

    def test_date_is_sunday(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17"))
        assert fm["date"] == "2026-04-26"

    def test_tags_include_year(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17"))
        assert "2026" in fm["tags"]

    def test_tags_include_portfolio(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17"))
        assert "portfolio" in fm["tags"]

    def test_draft_false(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17"))
        assert fm["draft"] is False

    def test_body_text(self):
        md = generate_markdown("2026-W17")
        assert "automated weekly portfolio log" in md

    def test_no_transactions_no_data_in_frontmatter(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17"))
        assert "transactions" not in fm
        assert "stats" not in fm


class TestPortfolioMarkdownWithData:
    def test_transactions_embedded(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17", _SAMPLE_TX))
        assert "transactions" in fm
        assert len(fm["transactions"]) == 2

    def test_buys_sorted_first(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17", _SAMPLE_TX))
        assert fm["transactions"][0]["type"] == "buy"
        assert fm["transactions"][1]["type"] == "sell"

    def test_transaction_fields(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17", _SAMPLE_TX))
        tx = fm["transactions"][0]
        assert tx["stock"] == "Apple Inc."
        assert tx["ticker"] == "AAPL"
        assert tx["isin"] == "US0378331005"
        assert tx["shares"] == 10
        assert tx["price_per_share"] == 150.25
        assert tx["total_amount"] == 1502.50
        assert tx["fees"] == 1.00
        assert tx["tax_withheld"] == 0.50
        assert tx["is_savings_plan"] is True

    def test_stats_computed(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17", _SAMPLE_TX))
        stats = fm["stats"]
        assert stats["total_invested"] == 1502.50
        assert stats["total_sold"] == 1000.00
        assert stats["total_fees"] == 2.00
        assert stats["total_tax"] == 3.75
        assert stats["buy_count"] == 1
        assert stats["sell_count"] == 1
        assert stats["savings_plan_count"] == 1

    def test_no_extra_fields_leaked(self):
        fm = _parse_frontmatter(generate_markdown("2026-W17", _SAMPLE_TX))
        tx = fm["transactions"][0]
        assert "week" not in tx
        assert "year" not in tx
