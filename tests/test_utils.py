"""Unit tests for shared utilities in utils.py and update_stats.py."""

import stat
from pathlib import Path

from update_stats import generate_markdown_list
from utils import (
    atomic_write_json,
    atomic_write_text,
    format_stars,
    get_github_headers,
    github_slug,
    infer_genre,
    load_games,
    normalize_game_entry,
    parse_github_url,
    save_games_atomic,
)


class TestUrlParsing:
    def test_https_standard_url(self):
        owner, repo = parse_github_url("https://github.com/Anuken/Mindustry")
        assert owner == "Anuken"
        assert repo == "Mindustry"

    def test_https_with_git_suffix(self):
        owner, repo = parse_github_url("https://github.com/yairm210/Unciv.git")
        assert owner == "yairm210"
        assert repo == "Unciv"

    def test_https_with_trailing_slash(self):
        owner, repo = parse_github_url("https://github.com/freeciv/freeciv/")
        assert owner == "freeciv"
        assert repo == "freeciv"

    def test_ssh_url(self):
        owner, repo = parse_github_url("git@github.com:00-Evan/shattered-pixel-dungeon.git")
        assert owner == "00-Evan"
        assert repo == "shattered-pixel-dungeon"

    def test_plain_owner_repo(self):
        owner, repo = parse_github_url("OpenTTD/OpenTTD")
        assert owner == "OpenTTD"
        assert repo == "OpenTTD"

    def test_plain_owner_repo_with_trailing_slash(self):
        owner, repo = parse_github_url("OpenTTD/OpenTTD/")
        assert owner == "OpenTTD"
        assert repo == "OpenTTD"

    def test_invalid_urls_and_phishing_hosts(self):
        assert parse_github_url("") == (None, None)
        assert parse_github_url("not a url") == (None, None)
        assert parse_github_url("https://gitlab.com/owner/repo") == (None, None)
        assert parse_github_url("https://fakegithub.com/owner/repo") == (None, None)
        assert parse_github_url("https://github.com.evil.com/owner/repo") == (None, None)


class TestStarFormatting:
    def test_under_thousand(self):
        assert format_stars(0) == "0"
        assert format_stars(42) == "42"
        assert format_stars(999) == "999"

    def test_thousands(self):
        assert format_stars(1000) == "1.0k"
        assert format_stars(1234) == "1.2k"
        assert format_stars(28666) == "28.7k"
        assert format_stars(999_900) == "999.9k"

    def test_boundary_and_millions(self):
        assert format_stars(999_950) == "1.0M"
        assert format_stars(1_000_000) == "1.0M"
        assert format_stars(2_540_000) == "2.5M"

    def test_invalid_input(self):
        assert format_stars("invalid") == "0"
        assert format_stars(None) == "0"


class TestGfmSlugs:
    def test_github_slug_generation(self):
        assert github_slug("Strategy & 4X") == "strategy--4x"
        assert github_slug("Roguelike & RPG") == "roguelike--rpg"
        assert github_slug("Sandbox & Simulation") == "sandbox--simulation"
        assert github_slug("Puzzle & Board") == "puzzle--board"
        assert github_slug("Arcade, Action & Racing") == "arcade-action--racing"
        assert github_slug("Casual & Adventure") == "casual--adventure"


class TestAtomicFileIO:
    def test_atomic_write_text_and_json(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        atomic_write_text(test_file, "hello world\n")
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "hello world\n"

        # Check permissions preserved
        mode_initial = stat.S_IMODE(test_file.stat().st_mode)
        atomic_write_text(test_file, "updated content\n")
        mode_after = stat.S_IMODE(test_file.stat().st_mode)
        assert mode_initial == mode_after
        assert test_file.read_text(encoding="utf-8") == "updated content\n"

        json_file = tmp_path / "data.json"
        data = [{"owner": "test", "repo": "game"}]
        atomic_write_json(json_file, data)
        loaded = load_games(json_file)
        assert loaded == data

        # Overwrite JSON
        save_games_atomic(data + [{"owner": "test2", "repo": "game2"}], json_file)
        loaded2 = load_games(json_file)
        assert len(loaded2) == 2


class TestHeadersAndAuth:
    def test_headers_without_token(self):
        headers = get_github_headers()
        assert "Accept" in headers
        assert "Authorization" not in headers

    def test_headers_with_token(self):
        headers = get_github_headers("ghp_dummy123")
        assert headers["Authorization"] == "token ghp_dummy123"


class TestGenreInferenceAndSchema:
    def test_infer_genre(self):
        assert infer_genre("Turn-based 4X civilization strategy") == "Strategy & 4X"
        assert infer_genre("Traditional roguelike dungeon crawler") == "Roguelike & RPG"
        assert infer_genre("Voxel sandbox world engine") == "Sandbox & Simulation"
        assert infer_genre("Fast 3D arcade kart racing") == "Arcade, Action & Racing"
        assert infer_genre("Sudoku number grid puzzle") == "Puzzle & Board"

    def test_normalize_game_entry_safe_with_nones(self):
        raw = {"owner": None, "repo": None, "description": None, "genre": None}
        normalized = normalize_game_entry(raw)
        assert normalized["owner"] == ""
        assert normalized["repo"] == ""
        assert normalized["stars"] == 0
        assert normalized["genre"] == "Casual & Adventure"

    def test_normalize_game_entry(self):
        raw = {
            "owner": "Anuken",
            "repo": "Mindustry",
            "name": "Mindustry",
            "description": "A sandbox tower-defense factory automation game",
            "tech": "Java / LibGDX",
            "stars": 28000,
            "genre": "Strategy & 4X",
        }
        normalized = normalize_game_entry(raw)
        assert normalized["owner"] == "Anuken"
        assert normalized["repo"] == "Mindustry"
        assert normalized["stars"] == 28000
        assert normalized["genre"] == "Strategy & 4X"
        assert normalized["default_branch"] == "main"
        assert normalized["archived"] is False


class TestMarkdownGeneration:
    def test_non_canonical_genres_preserved(self):
        games = [
            {"name": "Game A", "owner": "a", "repo": "a", "genre": "Strategy & 4X", "stars": 10},
            {"name": "Game B", "owner": "b", "repo": "b", "genre": "Rhythm", "stars": 20},
        ]
        md = generate_markdown_list(games, grouped=True)
        assert "Game A" in md
        assert "Game B" in md
        assert "Rhythm" in md

    def test_custom_genre_end_to_end_normalization(self):
        raw_custom = {
            "owner": "test",
            "repo": "rhythm-game",
            "name": "Rhythm Beats",
            "genre": "Rhythm & Music",
        }
        normalized = normalize_game_entry(raw_custom)
        assert normalized["genre"] == "Rhythm & Music"
        md = generate_markdown_list([normalized], grouped=True)
        assert "Rhythm & Music" in md
        assert "Rhythm Beats" in md
