#!/usr/bin/env python3
"""Awesome Android Games - GitHub Game Researcher.

Searches GitHub for active open-source Android games pushed > 2025,
verifies that releases contain downloadable APK files, and filters out non-game apps.
Supports async execution and rate limit detection.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

# Ensure src is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (  # noqa: E402
    ROOT_DIR,
    format_stars,
    get_github_headers,
    get_github_token,
    load_games,
    normalize_game_entry,
    save_games_atomic,
)

console = Console()

# Keywords and topics that confirm game domain
GAME_KEYWORDS = {
    "game",
    "games",
    "gaming",
    "arcade",
    "rpg",
    "roguelike",
    "puzzle",
    "platformer",
    "strategy",
    "simulator",
    "simulation",
    "chess",
    "sudoku",
    "tower-defense",
    "racing",
    "shooter",
    "action",
    "adventure",
    "libgdx",
    "godot",
    "flame",
    "pygame",
    "raylib",
    "sandbox",
    "voxel",
    "visual-novel",
    "trainer",
    "singing",
    "rhythm",
}

# Negative keywords to filter out non-game utility apps
NON_GAME_KEYWORDS = {
    "music-player",
    "audio-player",
    "video-player",
    "downloader",
    "browser",
    "launcher",
    "vpn",
    "proxy",
    "wallpaper",
    "keyboard",
    "messenger",
    "social",
    "file-manager",
    "backup",
    "camera",
    "comic",
    "translation",
}


def load_existing_repos() -> set[str]:
    """Load existing owner/repo combinations from games.json to avoid duplicates."""
    games = load_games()
    return {f"{g['owner'].lower()}/{g['repo'].lower()}" for g in games}


def is_game(repo_item: Dict[str, Any]) -> bool:
    """Heuristic check to ensure the repository is actually a game."""
    name = str(repo_item.get("name") or "").lower()
    desc = str(repo_item.get("description") or "").lower()
    topics = [str(t).lower() for t in repo_item.get("topics", [])]
    combined_text = f"{name} {desc} {' '.join(topics)}"

    has_non_game_match = any(w in combined_text for w in NON_GAME_KEYWORDS)
    has_game_match = any(w in combined_text for w in GAME_KEYWORDS)

    if has_non_game_match and not has_game_match:
        return False

    return has_game_match


async def check_release_apk_async(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    headers: Dict[str, str],
    sem: asyncio.Semaphore,
) -> Tuple[Optional[bool], Optional[str], Optional[str]]:
    """Check if repository has releases with downloadable .apk assets.

    Returns:
        (has_apk, release_tag, download_url)
        has_apk is None if rate-limited, network error, or 5xx occurs (unverified).
    """
    releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    async with sem:
        try:
            resp = await client.get(
                releases_url,
                headers=headers,
                params={"per_page": 100},
                timeout=12.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                releases = resp.json()
                for rel in releases:
                    tag = rel.get("tag_name", "")
                    assets = rel.get("assets", [])
                    for asset in assets:
                        name = str(asset.get("name") or "").lower()
                        if name.endswith(".apk"):
                            download_url = asset.get("browser_download_url")
                            return True, tag, download_url
                return False, None, None
            elif resp.status_code == 404:
                # Confirmed no releases exist
                return False, None, None
            elif resp.status_code == 403:
                reset_time = resp.headers.get("x-ratelimit-reset", "unknown")
                console.print(
                    f"[yellow]Rate limit reached checking releases for {owner}/{repo} "
                    f"(reset: {reset_time}).[/yellow]"
                )
                return None, None, None
            else:
                # 500, 502, 503, etc. -> unverified
                console.print(
                    f"[yellow]HTTP {resp.status_code} checking releases for {owner}/{repo}[/yellow]"
                )
                return None, None, None
        except Exception as e:
            console.print(f"[red]Network error checking releases for {owner}/{repo}: {e}[/red]")
            return None, None, None


async def search_android_games_async(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    pushed_after: str = "2025-01-01",
    min_stars: int = 15,
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    """Search GitHub for repositories matching Android game criteria pushed after specified date."""
    topics = [
        "android-game",
        "android-games",
        "libgdx",
        "libgdx-game",
        "godot-android",
        "roguelike android",
    ]
    dual_topics = [
        "android topic:game",
        "android topic:puzzle",
        "android topic:rpg",
    ]
    keywords = [
        '"android game"',
        '"open source android game"',
        '"libgdx" android',
        '"arcade game" android',
        '"puzzle game" android',
        '"tower defense" android',
        '"racing game" android',
        '"rpg game" android',
        '"card game" android',
        '"minesweeper" android',
        '"chess" android game',
        '"brain trainer" android',
        '"flame" flutter game android',
        '"pixel dungeon"',
    ]

    queries = (
        [f"topic:{t} pushed:>{pushed_after} stars:>={min_stars} fork:false" for t in topics]
        + [f"topic:{t} pushed:>{pushed_after} stars:>={min_stars} fork:false" for t in dual_topics]
        + [
            f"{kw} in:description pushed:>{pushed_after} stars:>={min_stars} fork:false"
            for kw in keywords
        ]
    )

    seen_repos = set()
    candidate_repos = []

    for q in queries:
        if len(candidate_repos) >= max_results:
            break
        search_url = "https://api.github.com/search/repositories"
        params = {
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": min(30, max_results - len(candidate_repos)),
        }
        try:
            resp = await client.get(search_url, headers=headers, params=params, timeout=15.0)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    full_name = str(item.get("full_name") or "").lower()
                    if full_name and full_name not in seen_repos:
                        seen_repos.add(full_name)
                        if is_game(item):
                            candidate_repos.append(item)
            elif resp.status_code == 403:
                console.print(
                    "[yellow]GitHub Search rate limit reached. "
                    "Authenticate via 'gh auth login' or provide --token.[/yellow]"
                )
                break
        except Exception as e:
            console.print(f"[red]Search error for query '{q}': {e}[/red]")

    return candidate_repos


async def main_async(args: argparse.Namespace) -> None:
    """Asynchronous main loop for researcher."""
    token = get_github_token(args.token)
    headers = get_github_headers(token)
    existing_repos = load_existing_repos()

    console.print(
        Panel.fit(
            f"[bold green]🔍 GitHub Android Game Researcher[/bold green]\n"
            f"• Pushed after: [cyan]{args.pushed_after}[/cyan]\n"
            f"• Min stars: [cyan]{args.min_stars}[/cyan]\n"
            f"• Require APK in Releases: [cyan]{args.require_apk}[/cyan]\n"
            f"• Already tracked games: [cyan]{len(existing_repos)}[/cyan]",
            border_style="cyan",
        )
    )

    sem = asyncio.Semaphore(10)
    async with httpx.AsyncClient() as client:
        console.print("[bold]Searching GitHub API for active Android game repositories...[/bold]")
        candidates = await search_android_games_async(
            client=client,
            headers=headers,
            pushed_after=args.pushed_after,
            min_stars=args.min_stars,
            max_results=args.limit,
        )

        console.print(
            f"Found [cyan]{len(candidates)}[/cyan] verified game candidates. "
            "Checking APK releases in parallel...\n"
        )

        # Check releases in parallel
        release_tasks = [
            check_release_apk_async(
                client=client,
                owner=item["owner"]["login"],
                repo=item["name"],
                headers=headers,
                sem=sem,
            )
            for item in candidates
        ]
        release_results = await asyncio.gather(*release_tasks)

        results = []
        for item, (has_apk, tag, apk_url) in zip(candidates, release_results):
            owner = item["owner"]["login"]
            repo = item["name"]
            full_name = f"{owner}/{repo}".lower()
            stars = item.get("stargazers_count", 0)
            pushed_at = str(item.get("pushed_at") or "")[:10]
            language = item.get("language") or "Android"
            desc = item.get("description") or "Open-source Android game"
            license_info = (item.get("license") or {}).get("spdx_id") or "Unknown"
            is_tracked = full_name in existing_repos

            # Filter logic: if APK required and confirmed no APK, skip
            if args.require_apk and has_apk is False:
                continue

            results.append(
                {
                    "owner": owner,
                    "repo": repo,
                    "name": item.get("name"),
                    "description": desc.strip(),
                    "tech": language,
                    "stars": stars,
                    "last_commit": pushed_at,
                    "license": license_info,
                    "has_apk": has_apk,
                    "release_tag": tag,
                    "apk_url": apk_url,
                    "is_tracked": is_tracked,
                    "default_branch": item.get("default_branch", "main"),
                    "archived": bool(item.get("archived", False)),
                    "language": language,
                }
            )

    # Render results table
    table = Table(title=f"Discovered Android Games (Pushed > {args.pushed_after} & APK Verified)")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Repository", style="bold white")
    table.add_column("Description", style="white", max_width=38)
    table.add_column("Stars", justify="right", style="yellow")
    table.add_column("Last Pushed", justify="center", style="cyan")
    table.add_column("Tech", style="magenta")
    table.add_column("License", style="green")
    table.add_column("APK Release", style="bold green")
    table.add_column("Tracked?", justify="center")

    new_qualifying_games = []
    for i, res in enumerate(results, 1):
        tracked_str = "[dim]Yes[/dim]" if res["is_tracked"] else "[bold cyan]NEW[/bold cyan]"
        if res["has_apk"] is True:
            apk_str = f"✓ {res['release_tag']}"
        elif res["has_apk"] is None:
            apk_str = "[yellow]Unverified[/yellow]"
        else:
            apk_str = "[dim]No APK[/dim]"

        table.add_row(
            str(i),
            f"{res['owner']}/{res['repo']}",
            res["description"][:36] + ("…" if len(res["description"]) > 36 else ""),
            format_stars(res["stars"]),
            res["last_commit"],
            res["tech"],
            res["license"],
            apk_str,
            tracked_str,
        )
        if not res["is_tracked"] and res["has_apk"] is True:
            new_qualifying_games.append(res)

    console.print(table)

    if not new_qualifying_games:
        console.print("[green]No new untracked games found with current criteria.[/green]")
        return

    console.print(
        f"\nFound [bold green]{len(new_qualifying_games)}[/bold green] new qualifying games."
    )

    should_add = args.auto_add
    if not should_add:
        try:
            should_add = Confirm.ask("Would you like to import these games into games.json?")
        except (EOFError, KeyboardInterrupt):
            console.print(
                "[yellow]Run with --auto-add to automatically import into "
                "games.json and update README.md[/yellow]"
            )
            should_add = False

    if should_add:
        games_list = load_games()
        for g in new_qualifying_games:
            games_list.append(normalize_game_entry(g))

        save_games_atomic(games_list)
        console.print(
            f"[bold green]✓ Added {len(new_qualifying_games)} new games to games.json![/bold green]"
        )
        console.print("[cyan]Running update_stats.py to refresh README.md...[/cyan]")
        subprocess.run(["uv", "run", "python", "src/update_stats.py"], cwd=ROOT_DIR, check=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search GitHub for active Android games pushed > 2025 with APK releases."
    )
    parser.add_argument(
        "--pushed-after",
        type=str,
        default="2025-01-01",
        help="Filter repos pushed after date YYYY-MM-DD (default: 2025-01-01)",
    )
    parser.add_argument(
        "--min-stars",
        type=int,
        default=15,
        help="Minimum stars threshold (default: 15)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Max number of candidate repositories to evaluate (default: 40)",
    )
    parser.add_argument(
        "--require-apk",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require downloadable .apk file in GitHub releases (use --no-require-apk to disable)",
    )
    parser.add_argument(
        "--auto-add",
        action="store_true",
        help="Automatically append discovered qualifying games to games.json without prompting",
    )
    parser.add_argument(
        "--token",
        type=str,
        help="GitHub Personal Access Token for 5,000 req/hr rate limit",
    )

    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
