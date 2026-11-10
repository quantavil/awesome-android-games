"""Unit tests for IssueOps event handling and issue form parsing."""

import json
from pathlib import Path
from typing import Any, Dict

import issueops_handler
from issueops_handler import handle_event, parse_command_args, parse_issue_markdown_form
from utils import load_games, save_games_atomic


def _use_temp_catalog(monkeypatch, tmp_path: Path) -> Path:
    fake_games_file = tmp_path / "games.json"
    save_games_atomic([], fake_games_file)
    monkeypatch.setattr("update_stats.load_games", lambda: load_games(fake_games_file))
    monkeypatch.setattr(
        "update_stats.save_games_atomic",
        lambda games: save_games_atomic(games, fake_games_file),
    )
    return fake_games_file


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
        "Hey maintainers, check out this game at https://github.com/foo/bar. It is really fun!"
    )
    parsed = parse_issue_markdown_form(sample_body)
    assert parsed["repo_url"] == "https://github.com/foo/bar"


def test_parse_command_args():
    cmd = "/add https://github.com/org/game --genre 'Puzzle & Logic' --tech Godot"
    parsed = parse_command_args(cmd)
    assert parsed["action"] == "add"
    assert parsed["url"] == "https://github.com/org/game"
    assert parsed["tech"] == "Godot"
    assert parsed["genre"] == "Puzzle & Logic"


def test_parse_command_args_keeps_quoted_multiword_name():
    parsed = parse_command_args('/add https://github.com/org/game --name "My Great Game"')
    assert parsed["name"] == "My Great Game"


def test_parse_command_args_unbalanced_quote_falls_back():
    parsed = parse_command_args("/add https://github.com/org/game --name 'Broken")
    assert parsed["url"] == "https://github.com/org/game"
    assert parsed["name"] == "'Broken"


def test_handle_event_add_update_and_remove(monkeypatch, tmp_path: Path):
    fake_games_file = _use_temp_catalog(monkeypatch, tmp_path)

    # 1. Add
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
    assert result_add["status"] == "added"
    assert len(load_games(fake_games_file)) == 1

    # 2. Same URL again updates the existing entry instead of duplicating it
    result_update = handle_event(add_event)
    assert result_update["success"] is True
    assert result_update["status"] == "updated"
    assert len(load_games(fake_games_file)) == 1

    # 3. Remove
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


def test_main_writes_only_json_to_stdout(monkeypatch, tmp_path: Path, capsys):
    """The workflow parses stdout as JSON, so catalog progress messages must not leak there."""
    _use_temp_catalog(monkeypatch, tmp_path)
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "comment": {"body": "/add https://github.com/author/stdout-check"},
                "issue": {"body": "", "labels": []},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(issueops_handler.sys, "argv", ["issueops", "--event-path", str(event_path)])

    issueops_handler.main()

    stdout = capsys.readouterr().out
    result = json.loads(stdout)
    assert result["success"] is True
