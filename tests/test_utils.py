"""Unit tests for shared utilities in utils.py."""

from pathlib import Path

from utils import (
    atomic_write_json,
    atomic_write_text,
    format_stars,
    get_github_headers,
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

    def test_invalid_urls(self):
        assert parse_github_url("") == (None, None)
        assert parse_github_url("not a url") == (None, None)
        assert parse_github_url("https://gitlab.com/owner/repo") == (None, None)


class TestStarFormatting:
    def test_under_thousand(self):
        assert format_stars(0) == "0"
        assert format_stars(42) == "42"
        assert format_stars(999) == "999"

    def test_thousands(self):
        assert format_stars(1000) == "1.0k"
        assert format_stars(1234) == "1.2k"
        assert format_stars(28666) == "28.7k"

    def test_millions(self):
        assert format_stars(1_000_000) == "1.0M"
        assert format_stars(2_540_000) == "2.5M"

    def test_invalid_input(self):
        assert format_stars("invalid") == "0"
        assert format_stars(None) == "0"


class TestAtomicFileIO:
    def test_atomic_write_text_and_json(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        atomic_write_text(test_file, "hello world\n")
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "hello world\n"

        # Overwrite atomically
        atomic_write_text(test_file, "updated content\n")
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

    def test_normalize_game_entry_without_genre(self):
        raw = {
            "owner": "freeciv",
            "repo": "freeciv",
            "description": "Turn-based 4X civilization strategy",
        }
        normalized = normalize_game_entry(raw)
        assert normalized["genre"] == "Strategy & 4X"
