"""Tests for the markdown generator."""

from src.dividends.generate_markdown import generate_markdown


class TestGenerateMarkdown:
    def test_contains_frontmatter(self):
        md = generate_markdown("2026-W17")
        assert "---" in md
        assert 'type: "weekly-report"' in md
        assert 'week: "2026-W17"' in md

    def test_title(self):
        md = generate_markdown("2026-W17")
        assert 'title: "Dividend Report – Week 17, 2026"' in md

    def test_date_is_sunday(self):
        md = generate_markdown("2026-W17")
        assert "date: 2026-04-26" in md

    def test_tags_include_year(self):
        md = generate_markdown("2026-W17")
        assert '"2026"' in md

    def test_draft_false(self):
        md = generate_markdown("2026-W17")
        assert "draft: false" in md
