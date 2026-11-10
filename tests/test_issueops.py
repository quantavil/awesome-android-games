"""Unit tests for IssueOps event handling and issue form parsing."""

from pathlib import Path
from typing import Any, Dict

from issueops_handler import handle_event, parse_command_args, parse_issue_markdown_form
from utils import load_games, save_games_atomic


def test_parse_issue_markdown_form_full():
    sample_body = """### Repository URL

https://github.com/test-owner/test-game

### Game Name (Optional)

Super Awesome Game

### Primary Genre

Strategy & 4X

### Engine / Technology Stack (Optional)

Godot / C#

### Brief Description (Optional)

A great space strategy game.
"""
    parsed = parse_issue_markdown_form(sample_body)
    assert parsed["repo_url"] == "https://github.com/test-owner/test-game"
    assert parsed["name"] == "Super Awesome Game"
    assert parsed["genre"] == "Strategy & 4X"
    assert parsed["tech"] == "Godot / C#"
    assert parsed["description"] == "A great space strategy game."


def test_parse_issue_markdown_form_raw_url_fallback():
    sample_body = (
        "Hey maintainers, check out this game at https://github.com/foo/bar. "
        "It is really fun!"
    )
    parsed = parse_issue_markdown_form(sample_body)
    assert parsed["repo_url"] == "https://github.com/foo/bar"


def test_parse_command_args():
    cmd = "/add https://github.com/org/game --genre 'Puzzle & Logic' --tech Godot"
    parsed = parse_command_args(cmd)
    assert parsed["action"] == "add"
    assert parsed["url"] == "https://github.com/org/game"
    assert parsed["tech"] == "Godot"


def test_handle_event_add_and_remove(monkeypatch, tmp_path: Path):
    fake_games_file = tmp_path / "games.json"
    save_games_atomic([], fake_games_file)

    monkeypatch.setattr("update_stats.load_games", lambda: load_games(fake_games_file))
    monkeypatch.setattr(
        "update_stats.save_games_atomic",
        lambda games: save_games_atomic(games, fake_games_file),
    )

    # 1. Event for Add
    add_event: Dict[str, Any] = {
        "comment": {"body": "/add https://github.com/author/new-arcade-game"},
        "issue": {
            "title": "[Game Submission]: New Arcade Game",
            "body": "",
            "labels": [{"name": "game-submission"}],
        },
    }
    result_add = handle_event(add_event)
    assert result_add["success"] is True
    assert result_add["action"] == "add"
    assert len(load_games(fake_games_file)) == 1

    # 2. Event for Remove
    remove_event: Dict[str, Any] = {
        "comment": {"body": "/remove https://github.com/author/new-arcade-game"},
        "issue": {
            "title": "[Removal Request]: New Arcade Game",
            "body": "",
            "labels": [{"name": "game-removal"}],
        },
    }
    result_remove = handle_event(remove_event)
    assert result_remove["success"] is True
    assert result_remove["action"] == "remove"
    assert len(load_games(fake_games_file)) == 0


def test_handle_event_invalid_url():
    event: Dict[str, Any] = {
        "comment": {"body": "/add not-a-valid-url"},
        "issue": {"body": "", "labels": []},
    }
    result = handle_event(event)
    assert result["success"] is False
