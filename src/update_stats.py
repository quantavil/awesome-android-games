#!/usr/bin/env python3
"""Awesome Android Games - GitHub Stats Updater.

Fetches real-time stars, latest commits, license info, and updates README.md.
Supports async concurrency, categorized genre grouping, and atomic file writes.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
from rich.console import Console
from rich.table import Table

# Ensure src is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (  # noqa: E402
    GENRE_CATEGORIES,
    README_PATH,
    atomic_write_text,
    format_stars,
    get_github_headers,
    get_github_token,
    github_slug,
    infer_genre,
    load_games,
    normalize_game_entry,
    parse_github_url,
    save_games_atomic,
)

console = Console()

START_MARKER = "<!-- GAMES_LIST_START -->"
END_MARKER = "<!-- GAMES_LIST_END -->"
COUNT_MARKER_REGEX = r"<!-- TOTAL_GAMES_COUNT -->.*?<!-- /TOTAL_GAMES_COUNT -->"
UPDATED_MARKER_REGEX = r"<!-- LAST_UPDATED -->.*?<!-- /LAST_UPDATED -->"


async def fetch_repo_stats_async(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    headers: Dict[str, str],
    sem: asyncio.Semaphore,
    cached_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fetch repo metadata asynchronously from GitHub API with rate limit preservation."""
    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    stats: Dict[str, Any] = {
        "stars": cached_stats.get("stars", 0) if cached_stats else 0,
        "last_commit": cached_stats.get("last_commit", "N/A") if cached_stats else "N/A",
        "license": cached_stats.get("license", "Unknown") if cached_stats else "Unknown",
        "default_branch": cached_stats.get("default_branch", "main") if cached_stats else "main",
        "archived": cached_stats.get("archived", False) if cached_stats else False,
        "language": cached_stats.get("language") if cached_stats else None,
    }

    async with sem:
        try:
            resp = await client.get(repo_url, headers=headers, timeout=12.0, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                stats["stars"] = data.get("stargazers_count", stats["stars"])
                stats["archived"] = data.get("archived", stats["archived"])
                stats["language"] = data.get("language", stats["language"])
                if data.get("license") and data["license"].get("spdx_id"):
                    spdx = data["license"]["spdx_id"]
                    if spdx != "NOASSERTION":
                        stats["license"] = spdx
                stats["default_branch"] = data.get("default_branch", "main")

                # Auto-fill missing/placeholder metadata directly from GitHub
                if cached_stats:
                    curr_desc = cached_stats.get("description", "")
                    if (not curr_desc or curr_desc == "Open-source Android game.") and data.get(
                        "description"
                    ):
                        stats["description"] = data["description"].strip()
                    if not cached_stats.get("name") or cached_stats.get("name") == repo:
                        if data.get("name"):
                            stats["name"] = data["name"].strip()
                    if not cached_stats.get("genre"):
                        topics = " ".join(data.get("topics", []))
                        name_desc = f"{data.get('name', '')} {data.get('description', '')}"
                        stats["genre"] = infer_genre(f"{name_desc} {topics}")

                pushed_at = data.get("pushed_at")
                if pushed_at:
                    stats["last_commit"] = pushed_at.split("T")[0]
            elif resp.status_code == 403:
                console.print(
                    f"[yellow]Rate limit for {owner}/{repo}. Using cached stats.[/yellow]"
                )
            else:
                console.print(
                    f"[yellow]Failed {owner}/{repo} (HTTP {resp.status_code}). "
                    "Cached stats kept.[/yellow]"
                )
        except Exception as e:
            console.print(f"[red]Error fetching {owner}/{repo}: {e}. Using cached stats.[/red]")

    return stats


def generate_game_markdown_item(game: Dict[str, Any]) -> str:
    """Generate Markdown bullet line for a single game."""
    name = game.get("name", game["repo"])
    url = f"https://github.com/{game['owner']}/{game['repo']}"
    desc = game.get("description", "").strip()
    tech = game.get("tech") or game.get("language") or "Android"
    stars_formatted = format_stars(game.get("stars", 0))
    last_commit = game.get("last_commit", "N/A")
    license_str = game.get("license", "")
    archived_badge = " *(Archived)*" if game.get("archived") else ""

    meta_parts = [
        f"⭐ **{stars_formatted}**",
        f"Last updated: `{last_commit}`",
        f"`{tech}`",
    ]
    if license_str and license_str not in ("Unknown", "NOASSERTION"):
        meta_parts.append(f"`{license_str}`")

    meta_line = " · ".join(meta_parts)
    return f"- **[{name}]({url})**{archived_badge} : {desc}\n  - {meta_line}"


def generate_markdown_list(games: List[Dict[str, Any]], grouped: bool = True) -> str:
    """Generate Markdown representation of games list, dynamically preserving all categories."""
    if not grouped:
        return "\n".join(generate_game_markdown_item(g) for g in games)

    # Category Grouped format with Quick Navigation TOC
    toc_lines = ["### Categories\n"]
    category_map: Dict[str, List[Dict[str, Any]]] = {genre: [] for genre in GENRE_CATEGORIES}

    for game in games:
        genre = game.get("genre") or "Casual & Adventure"
        if genre not in category_map:
            category_map[genre] = []
        category_map[genre].append(game)

    # Active genres: canonical in predefined order, then any custom categories sorted alphabetically
    canonical_active = [g for g in GENRE_CATEGORIES if category_map.get(g)]
    custom_active = sorted(
        [g for g in category_map if g not in GENRE_CATEGORIES and category_map[g]]
    )
    active_genres = canonical_active + custom_active

    for genre in active_genres:
        slug = github_slug(genre)
        count = len(category_map[genre])
        toc_lines.append(f"- [{genre}](#{slug}) ({count})")

    content_sections = ["\n".join(toc_lines), "\n---"]

    for genre in active_genres:
        genre_games = category_map[genre]
        content_sections.append(f"\n### {genre}\n")
        for g in genre_games:
            content_sections.append(generate_game_markdown_item(g))

    return "\n".join(content_sections)


def update_readme(markdown_list: str, total_count: int) -> bool:
    """Update README.md with generated markdown content between markers atomically."""
    if not README_PATH.exists():
        console.print(f"[red]Error: {README_PATH} not found![/red]")
        return False

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        console.print(
            f"[red]Error: Markers {START_MARKER} and {END_MARKER} not found in {README_PATH}[/red]"
        )
        return False

    pattern = re.compile(rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}", re.DOTALL)
    replacement = f"{START_MARKER}\n{markdown_list}\n{END_MARKER}"
    new_content = pattern.sub(replacement, content)

    # Update badge counters cleanly with markers outside the HTML src attribute
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    today_badge = today.replace("-", "--")
    count_replacement = (
        f'<!-- TOTAL_GAMES_COUNT --><a href="#games-list">'
        f'<img src="https://img.shields.io/badge/Games-{total_count}-3ddc84.svg?style=flat-square" '
        f'alt="Tracked Games" /></a><!-- /TOTAL_GAMES_COUNT -->'
    )
    updated_replacement = (
        f'<!-- LAST_UPDATED --><a href="#games-list">'
        f'<img src="https://img.shields.io/badge/Updated-{today_badge}-blueviolet.svg'
        '?style=flat-square" '
        'alt="Last Updated" /></a><!-- /LAST_UPDATED -->'
    )

    new_content = re.sub(COUNT_MARKER_REGEX, count_replacement, new_content)
    new_content = re.sub(UPDATED_MARKER_REGEX, updated_replacement, new_content)

    atomic_write_text(README_PATH, new_content)
    return True


def add_game(
    url: str,
    name: Optional[str] = None,
    desc: Optional[str] = None,
    tech: Optional[str] = None,
    genre: Optional[str] = None,
) -> None:
    """Add or update a game repository in games.json."""
    owner, repo = parse_github_url(url)
    if not owner or not repo:
        console.print(f"[red]Error: Invalid GitHub repository URL or format: '{url}'[/red]")
        return

    games = load_games()
    for g in games:
        if g["owner"].lower() == owner.lower() and g["repo"].lower() == repo.lower():
            console.print(
                f"[yellow]Game {owner}/{repo} already exists in games.json. "
                "Updating details...[/yellow]"
            )
            if name:
                g["name"] = name
            if desc:
                g["description"] = desc
            if tech:
                g["tech"] = tech
            if genre:
                g["genre"] = genre
            save_games_atomic([normalize_game_entry(item) for item in games])
            console.print(f"[green]Successfully updated {owner}/{repo}![/green]")
            return

    new_entry = normalize_game_entry(
        {
            "owner": owner,
            "repo": repo,
            "name": name or repo,
            "description": desc or "Open-source Android game.",
            "tech": tech or "Android",
            "genre": genre,
        }
    )
    games.append(new_entry)
    save_games_atomic(games)
    console.print(f"[green]Added {owner}/{repo} to games.json ({len(games)} total games)![/green]")


def get_sort_key(sort_mode: str) -> tuple[Callable[[Dict[str, Any]], Any], bool]:
    """Return sort key function and reverse boolean."""
    if sort_mode == "stars":
        return lambda g: g.get("stars", 0), True
    elif sort_mode == "name":
        return lambda g: g.get("name", g["repo"]).lower(), False
    elif sort_mode == "genre":
        return lambda g: (g.get("genre", ""), g.get("stars", 0)), True
    # Default: "updated"
    return (
        lambda g: (
            g["last_commit"] if g.get("last_commit") not in (None, "N/A") else "0000-00-00",
            g.get("stars", 0),
        ),
        True,
    )


async def main_async(args: argparse.Namespace) -> None:
    """Asynchronous entry point for stats updater."""
    if args.add:
        add_game(args.add, name=args.name, desc=args.desc, tech=args.tech, genre=args.genre)

    games = load_games()
    if not games:
        console.print("[red]No games found in games.json.[/red]")
        sys.exit(1)

    console.print(
        f"[bold cyan]Fetching live stats for {len(games)} games asynchronously...[/bold cyan]"
    )

    token = get_github_token(args.token)
    headers = get_github_headers(token)
    sem = asyncio.Semaphore(10)

    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_repo_stats_async(
                client=client,
                owner=game["owner"],
                repo=game["repo"],
                headers=headers,
                sem=sem,
                cached_stats=game,
            )
            for game in games
        ]
        results = await asyncio.gather(*tasks)

        for game, stats in zip(games, results):
            game.update(stats)
            # If tech was generic default and language was discovered, upgrade tech
            if game.get("tech") in ("Android", "Kotlin/Java") and stats.get("language"):
                game["tech"] = stats["language"]

    # Persist updated stats atomically
    normalized_games = [normalize_game_entry(g) for g in games]
    save_games_atomic(normalized_games)

    # Apply sorting globally and within category groups
    sort_key, reverse_order = get_sort_key(args.sort)
    normalized_games.sort(key=sort_key, reverse=reverse_order)

    # Display preview table in console
    table = Table(title="Awesome Android Games - Live Stats")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Game", style="bold white")
    table.add_column("Genre", style="cyan")
    table.add_column("Stars", justify="right", style="yellow")
    table.add_column("Last Updated", justify="center", style="green")
    table.add_column("Tech / Engine", style="magenta")
    table.add_column("License", style="dim")

    for i, g in enumerate(normalized_games, 1):
        table.add_row(
            str(i),
            g.get("name", g["repo"]),
            g.get("genre", "General"),
            format_stars(g.get("stars", 0)),
            g.get("last_commit", "N/A"),
            g.get("tech") or g.get("language") or "Android",
            g.get("license", "Unknown"),
        )

    console.print(table)

    # Generate Markdown (grouped mode unless --flat is explicitly passed)
    markdown_list = generate_markdown_list(normalized_games, grouped=not args.flat)

    if args.dry_run:
        console.print("\n[bold]Generated Markdown Output:[/bold]\n")
        print(markdown_list)
    else:
        if update_readme(markdown_list, len(normalized_games)):
            console.print(
                f"[bold green]✓ Successfully updated README.md with "
                f"{len(normalized_games)} games![/bold green]"
            )
        else:
            console.print(
                "[yellow]Tip: Ensure README.md exists with markers "
                "<!-- GAMES_LIST_START --> and <!-- GAMES_LIST_END -->[/yellow]"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Awesome Android Games - Stats Updater")
    parser.add_argument(
        "--sort",
        choices=["updated", "stars", "name", "genre"],
        default="updated",
        help="Sorting criteria for games within categories or flat list (default: updated)",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Generate a single flat list instead of categorizing by genre",
    )
    parser.add_argument(
        "--add",
        type=str,
        help="Add a new game by GitHub URL or owner/repo (e.g., https://github.com/Anuken/Mindustry)",
    )
    parser.add_argument("--name", type=str, help="Game display name (used with --add)")
    parser.add_argument("--desc", type=str, help="Game description (used with --add)")
    parser.add_argument("--tech", type=str, help="Tech stack/engine (used with --add)")
    parser.add_argument("--genre", type=str, help="Genre/category (used with --add)")
    parser.add_argument(
        "--token",
        type=str,
        help="GitHub Personal Access Token to bypass API rate limits",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print markdown list to stdout without writing to README.md",
    )

    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
