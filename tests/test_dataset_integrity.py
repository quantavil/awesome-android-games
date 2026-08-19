"""Integration tests for games.json schema integrity and README synchronization."""

import json
import re

from utils import GAMES_JSON_PATH, GENRE_CATEGORIES, README_PATH, github_slug


class TestDatasetIntegrity:
    def test_games_json_exists_and_valid(self):
        assert GAMES_JSON_PATH.exists(), "games.json must exist"
        with open(GAMES_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list), "games.json must be a list of game objects"
        assert len(data) > 0, "games.json must not be empty"

    def test_games_schema_fields(self):
        with open(GAMES_JSON_PATH, "r", encoding="utf-8") as f:
            games = json.load(f)

        required_keys = {
            "owner",
            "repo",
            "name",
            "description",
            "tech",
            "stars",
            "last_commit",
            "license",
        }

        for i, game in enumerate(games):
            assert isinstance(game, dict), f"Game at index {i} must be a dictionary"
            for key in required_keys:
                assert key in game, f"Game '{game.get('repo', i)}' missing required key '{key}'"
                assert game[key] is not None, f"Game '{game.get('repo', i)}' has None for '{key}'"
            assert isinstance(game["stars"], int), f"Game '{game['repo']}' stars must be integer"
            assert game["stars"] >= 0, f"Game '{game['repo']}' stars cannot be negative"
            assert len(game["owner"]) > 0, f"Game at index {i} has empty owner"
            assert len(game["repo"]) > 0, f"Game at index {i} has empty repo"

    def test_no_duplicate_repositories(self):
        with open(GAMES_JSON_PATH, "r", encoding="utf-8") as f:
            games = json.load(f)

        seen = set()
        duplicates = []
        for g in games:
            slug = f"{g['owner'].lower()}/{g['repo'].lower()}"
            if slug in seen:
                duplicates.append(slug)
            seen.add(slug)

        assert not duplicates, f"Duplicate repositories found in games.json: {duplicates}"


class TestReadmeSynchronization:
    def test_readme_markers_exist(self):
        assert README_PATH.exists(), "README.md must exist"
        content = README_PATH.read_text(encoding="utf-8")
        assert "<!-- GAMES_LIST_START -->" in content
        assert "<!-- GAMES_LIST_END -->" in content
        assert "<!-- TOTAL_GAMES_COUNT -->" in content
        assert "<!-- LAST_UPDATED -->" in content

    def test_readme_badge_count_matches_dataset(self):
        with open(GAMES_JSON_PATH, "r", encoding="utf-8") as f:
            games = json.load(f)

        content = README_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"<!-- TOTAL_GAMES_COUNT -->.*?(\d+).*?<!-- /TOTAL_GAMES_COUNT -->",
            content,
        )
        assert match is not None, "TOTAL_GAMES_COUNT badge marker not found in README.md"
        badge_count = int(match.group(1))
        assert badge_count == len(games), (
            f"README count badge ({badge_count}) does not match games.json total ({len(games)})"
        )

    def test_all_games_in_readme(self):
        with open(GAMES_JSON_PATH, "r", encoding="utf-8") as f:
            games = json.load(f)

        content = README_PATH.read_text(encoding="utf-8")
        for g in games:
            url_fragment = f"github.com/{g['owner']}/{g['repo']}"
            assert url_fragment.lower() in content.lower(), (
                f"Repository {g['owner']}/{g['repo']} missing from README.md"
            )

    def test_toc_anchor_links_match_gfm_headings(self):
        """Ensure all TOC links match exact GitHub-rendered heading slugs."""
        content = README_PATH.read_text(encoding="utf-8")
        for genre in GENRE_CATEGORIES:
            heading = f"### {genre}"
            if heading in content:
                expected_anchor = f"(#{github_slug(genre)})"
                assert expected_anchor in content, (
                    f"TOC link for '{genre}' does not match expected GFM anchor '{expected_anchor}'"
                )
