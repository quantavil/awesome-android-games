"""Tests for stats fetching, README rendering, and catalog writes.

Network calls are served by httpx.MockTransport, so these tests never reach GitHub.
"""

import asyncio
import base64
from pathlib import Path

import httpx

import update_stats
from update_stats import (
    add_game,
    fetch_repo_stats_async,
    generate_game_markdown_item,
    update_readme,
)
from utils import (
    PLACEHOLDER_DESCRIPTION,
    detect_license_from_text,
    escape_markdown_text,
    load_games,
    normalize_game_entry,
    save_games_atomic,
)

GPL3_TEXT = (
    "                    GNU GENERAL PUBLIC LICENSE\n"
    "                       Version 3, 29 June 2007\n"
)


def _cached(**overrides):
    base = {
        "owner": "o",
        "repo": "r",
        "name": "r",
        "description": PLACEHOLDER_DESCRIPTION,
        "genre": "",
        "stars": 0,
        "last_commit": "N/A",
        "license": "NOASSERTION",
        "language": None,
        "host": "github.com",
    }
    base.update(overrides)
    return base


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_detect_license_from_common_texts():
    assert detect_license_from_text(GPL3_TEXT) == "GPL-3.0"
    assert detect_license_from_text("Apache License\nVersion 2.0, January 2004") == "Apache-2.0"
    mit = "Permission is hereby granted, free of charge, to any person obtaining a copy"
    assert detect_license_from_text(mit) == "MIT"
    assert detect_license_from_text("Some custom terms") is None


def test_detect_license_handles_gpl_notice_and_zlib():
    notice = (
        "Tensy Copyright (C) 2024 ROllerozxa\n\nThis program is free software: you can\n"
        "redistribute it and/or modify it under the terms of the GNU General\n"
        "Public License as published by the Free Software Foundation, either\n"
        "version 3 of the License, or (at your option) any later version.\n"
    )
    assert detect_license_from_text(notice) == "GPL-3.0"
    zlib = (
        "This software is provided 'as-is', without any express or implied warranty.\n"
        "Altered source versions must be plainly marked as such."
    )
    assert detect_license_from_text(zlib) == "Zlib"


def test_detect_license_distinguishes_bsd_2_and_3():
    base = "Redistribution and use in source and binary forms, with or without modification"
    assert detect_license_from_text(base) == "BSD-2-Clause"
    assert detect_license_from_text(base + ". Neither the name of the copyright holder") == (
        "BSD-3-Clause"
    )


def test_detect_license_refuses_to_guess_on_multiple_licenses():
    bundled = (
        "Apache License\nVersion 2.0, January 2004\n\n"
        "Textures are licensed under the GNU Lesser General Public License\n"
        "version 2.1 as published by the Free Software Foundation."
    )
    assert detect_license_from_text(bundled) is None


def test_escape_markdown_text_blocks_injection():
    escaped = escape_markdown_text("A [b] <!-- GAMES_LIST_END --> <script>")
    assert "<!--" not in escaped
    assert "<script>" not in escaped
    assert "\\[b\\]" in escaped


def test_markdown_item_escapes_name_and_description():
    item = generate_game_markdown_item(
        {
            "owner": "o",
            "repo": "r",
            "name": "A [b]",
            "description": "x <!-- GAMES_LIST_END --> y",
            "stars": 1,
            "last_commit": "2026-01-01",
            "tech": "Kotlin",
            "license": "MIT",
        }
    )
    assert "[A \\[b\\]](https://github.com/o/r)" in item
    assert "<!--" not in item


def test_normalize_does_not_guess_genre_from_placeholder():
    entry = normalize_game_entry(
        {"owner": "o", "repo": "r", "name": "Puzzle Thing", "description": PLACEHOLDER_DESCRIPTION}
    )
    assert entry["genre"] == ""


def test_add_game_reports_added_then_updated(monkeypatch, tmp_path: Path):
    games_file = tmp_path / "games.json"
    save_games_atomic([], games_file)
    monkeypatch.setattr("update_stats.load_games", lambda: load_games(games_file))
    monkeypatch.setattr(
        "update_stats.save_games_atomic", lambda games: save_games_atomic(games, games_file)
    )

    assert add_game("https://github.com/o/new") == "added"
    assert add_game("https://github.com/o/new", genre="Puzzle & Logic") == "updated"
    assert add_game("not a url") is None
    assert load_games(games_file)[0]["genre"] == "Puzzle & Logic"


async def test_github_fetch_fills_placeholder_and_detects_license():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/license"):
            content = base64.b64encode(GPL3_TEXT.encode()).decode()
            return httpx.Response(200, json={"content": content})
        return httpx.Response(
            200,
            json={
                "stargazers_count": 42,
                "archived": False,
                "language": "Kotlin",
                "default_branch": "main",
                "license": {"spdx_id": "NOASSERTION"},
                "description": "A real puzzle description",
                "topics": ["puzzle"],
                "name": "r",
                "pushed_at": "2026-01-02T00:00:00Z",
            },
        )

    async with _client(handler) as client:
        stats = await fetch_repo_stats_async(
            client, "o", "r", {}, asyncio.Semaphore(2), cached_stats=_cached()
        )

    assert stats["stars"] == 42
    assert stats["license"] == "GPL-3.0"
    assert stats["description"] == "A real puzzle description"
    assert stats["genre"] == "Puzzle & Logic"
    assert stats["last_commit"] == "2026-01-02"


async def test_gitlab_fetch_replaces_placeholder_description():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "star_count": 9,
                "archived": False,
                "default_branch": "main",
                "last_activity_at": "2026-03-04T10:00:00Z",
                "description": "Gitlab description",
            },
        )

    async with _client(handler) as client:
        stats = await fetch_repo_stats_async(
            client,
            "group/sub",
            "repo",
            {},
            asyncio.Semaphore(2),
            cached_stats=_cached(host="gitlab.com"),
            host="gitlab.com",
        )
    assert stats["description"] == "Gitlab description"
    assert stats["stars"] == 9


async def test_forgejo_null_language_keeps_cached_value():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"stars_count": 3, "archived": False, "language": None, "updated_at": None},
        )

    async with _client(handler) as client:
        stats = await fetch_repo_stats_async(
            client,
            "o",
            "r",
            {},
            asyncio.Semaphore(2),
            cached_stats=_cached(host="codeberg.org", language="Java"),
            host="codeberg.org",
        )
    assert stats["language"] == "Java"


async def test_unsupported_host_makes_no_request_and_keeps_cache():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected for hosts without a live API")

    async with _client(handler) as client:
        stats = await fetch_repo_stats_async(
            client,
            "~owner",
            "repo",
            {},
            asyncio.Semaphore(2),
            cached_stats=_cached(host="git.sr.ht", stars=5),
            host="git.sr.ht",
        )
    assert stats["stars"] == 5


def test_update_readme_replaces_block_and_badges(monkeypatch, tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Title\n"
        "<!-- TOTAL_GAMES_COUNT --><a>old</a><!-- /TOTAL_GAMES_COUNT -->\n"
        "<!-- LAST_UPDATED --><a>old</a><!-- /LAST_UPDATED -->\n"
        "<!-- GAMES_LIST_START -->\nold list\n<!-- GAMES_LIST_END -->\n"
        "footer\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(update_stats, "README_PATH", readme)

    assert update_readme("- new item \\[x\\]", 7) is True

    content = readme.read_text(encoding="utf-8")
    assert "old list" not in content
    assert "- new item \\[x\\]" in content
    assert "Games-7-" in content
    assert "footer" in content
