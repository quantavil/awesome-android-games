"""Integration tests for games.json schema integrity and README synchronization."""

import json
import re

from utils import GAMES_JSON_PATH, GENRE_CATEGORIES, README_PATH, ROOT_DIR, github_slug

TEMPLATE_DIR = ROOT_DIR / ".github" / "ISSUE_TEMPLATE"
NON_CANONICAL_OPTIONS = {"No change", "Other / Let script infer"}


def _load_games():
    with open(GAMES_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestDatasetIntegrity:
    def test_games_json_exists_and_valid(self):
        assert GAMES_JSON_PATH.exists(), "games.json must exist"
        data = _load_games()
        assert isinstance(data, list), "games.json must be a list of game objects"
        assert len(data) > 0, "games.json must not be empty"

    def test_games_schema_fields(self):
        games = _load_games()

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
        seen = set()
        duplicates = []
        for g in _load_games():
            host = g.get("host", "github.com").lower()
            slug = f"{host}/{g['owner'].lower()}/{g['repo'].lower()}"
            if slug in seen:
                duplicates.append(slug)
            seen.add(slug)

        assert not duplicates, f"Duplicate repositories found in games.json: {duplicates}"

    def test_every_game_has_a_genre_from_the_canonical_list(self):
        unknown = {
            g["repo"]: g.get("genre")
            for g in _load_games()
            if g.get("genre") not in GENRE_CATEGORIES
        }
        assert not unknown, f"Games with a genre outside GENRE_CATEGORIES: {unknown}"


class TestIssueTemplateSync:
    def test_genre_dropdowns_match_canonical_list(self):
        """The YAML forms cannot import GENRE_CATEGORIES, so keep their options in lockstep."""
        for name in ("add-game.yml", "update-game.yml"):
            text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
            options = [
                option
                for option in re.findall(r'^\s+- "([^"]+)"\s*$', text, re.MULTILINE)
                if option not in NON_CANONICAL_OPTIONS
            ]
            assert options == GENRE_CATEGORIES, (
                f"{name} genre options drifted from GENRE_CATEGORIES"
            )


class TestReadmeSynchronization:
    def test_readme_markers_exist(self):
        assert README_PATH.exists(), "README.md must exist"
        content = README_PATH.read_text(encoding="utf-8")
        assert "<!-- GAMES_LIST_START -->" in content
        assert "<!-- GAMES_LIST_END -->" in content
        assert "<!-- TOTAL_GAMES_COUNT -->" in content
        assert "<!-- LAST_UPDATED -->" in content

    def test_readme_badge_count_matches_dataset(self):
        games = _load_games()

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

    def test_every_game_links_to_its_exact_url(self):
        content = README_PATH.read_text(encoding="utf-8")
        for g in _load_games():
            host = g.get("host", "github.com")
            url = f"https://{host}/{g['owner']}/{g['repo']}"
            assert f"]({url})" in content, f"README is missing the exact link for {url}"

    def test_toc_links_resolve_to_real_headings(self):
        """Each category link in the table of contents must point at an existing heading."""
        content = README_PATH.read_text(encoding="utf-8")
        headings = {github_slug(h.strip()) for h in re.findall(r"^### (.+)$", content, re.M)}
        toc_anchors = re.findall(r"^- \[[^\]]+\]\(#([^)]+)\)", content, re.M)
        assert toc_anchors, "no table-of-contents links found in README.md"
        missing = [anchor for anchor in toc_anchors if anchor not in headings]
        assert not missing, f"TOC anchors without a matching heading: {missing}"
