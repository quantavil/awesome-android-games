"""Shared utilities for Awesome Android Games.

Provides atomic file IO, robust GitHub URL parsing, API authentication,
star formatting, GFM slug generation, and dataset normalization.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
GAMES_JSON_PATH = ROOT_DIR / "games.json"
README_PATH = ROOT_DIR / "README.md"

GENRE_CATEGORIES: List[str] = [
    "Strategy & 4X",
    "Roguelike & RPG",
    "Sandbox & Simulation",
    "Puzzle & Board",
    "Arcade, Action & Racing",
    "Casual & Adventure",
]

# Mapping rules from keywords / topics to canonical genres (ordered by specificity)
GENRE_MAPPINGS: Dict[str, List[str]] = {
    "Roguelike & RPG": [
        "pixel dungeon",
        "roguelike",
        "rpg",
        "dungeon",
        "crawler",
        "quest",
        "fantasy",
        "cataclysm",
        "turn-based rpg",
    ],
    "Puzzle & Board": [
        "puzzle",
        "sudoku",
        "minesweeper",
        "chess",
        "ludo",
        "uno",
        "card game",
        "solitaire",
        "board",
        "word puzzle",
        "knot",
        "chain relations",
        "tic tac toe",
        "2048",
        "tetris",
        "15 puzzle",
        "tangler",
        "brain trainer",
        "math trainer",
        "focus",
    ],
    "Sandbox & Simulation": [
        "voxel",
        "sandbox",
        "simulation",
        "simulator",
        "transport tycoon",
        "game of life",
    ],
    "Strategy & 4X": [
        "civilization",
        "4x",
        "strategy",
        "tower-defense",
        "tower defense",
        "automation",
        "factory",
        "tactics",
        "rts",
        "real-time strategy",
    ],
    "Arcade, Action & Racing": [
        "racing",
        "kart",
        "arcade",
        "action",
        "shooter",
        "pinball",
        "brick-breaking",
        "brick blast",
        "platformer",
        "runner",
        "flappy",
        "retro arcade",
    ],
    "Casual & Adventure": [
        "casual",
        "adventure",
        "story",
        "visual novel",
        "drifting",
        "singing",
        "rhythm",
    ],
}


def github_slug(text: str) -> str:
    """Generate exact GitHub Flavored Markdown (GFM) header anchor slug."""
    text = text.lower()
    # Strip all characters except word characters, whitespace, and hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace space characters with hyphens
    return re.sub(r" ", "-", text)


def infer_genre(text: str) -> str:
    """Infer canonical genre from title, description, or topics."""
    text_lower = text.lower()
    for genre, keywords in GENRE_MAPPINGS.items():
        if any(kw in text_lower for kw in keywords):
            return genre
    return "Casual & Adventure"


def format_stars(count: int) -> str:
    """Format star count into compact human-readable string (e.g. 1.2k, 28.7k, 1.0M)."""
    try:
        count = int(count)
    except (ValueError, TypeError):
        return "0"

    # Avoid boundary rounding artifact where 999_950 formats to '1000.0k'
    if count >= 999_950:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def parse_github_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract owner and repo name from GitHub URL, SSH git path, or owner/repo string.

    Supports:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo/
    - https://github.com/owner/repo/tree/main
    - git@github.com:owner/repo.git
    - owner/repo
    - owner/repo/
    """
    if not url:
        return None, None

    clean = url.strip()

    # SSH pattern: git@github.com:owner/repo.git
    ssh_match = re.match(r"^git@github\.com:([^/\s]+)/([^/\s#]+?)(?:\.git)?/?$", clean)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2).removesuffix(".git")

    # HTTP/HTTPS URLs (strictly validate github.com hostname)
    if clean.startswith("http://") or clean.startswith("https://"):
        parsed = urlparse(clean)
        if parsed.netloc.lower() in ("github.com", "www.github.com"):
            parts = [p for p in parsed.path.strip("/").split("/") if p]
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1].removesuffix(".git")
                return owner, repo
        return None, None

    # Plain owner/repo format (allowing trailing slashes / .git)
    clean_slug = clean.strip("/")
    parts = [p for p in clean_slug.split("/") if p]
    if len(parts) == 2 and not clean.startswith("http"):
        return parts[0], parts[1].removesuffix(".git")

    return None, None


def get_github_token(explicit_token: Optional[str] = None) -> Optional[str]:
    """Retrieve GitHub token from explicit arg, env variables, or gh CLI."""
    if explicit_token:
        return explicit_token
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_github_headers(token: Optional[str] = None) -> Dict[str, str]:
    """Build standard GitHub API request headers."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Awesome-Android-Games-Updater/1.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def atomic_write_text(file_path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically write text content to file using temp file, ensuring standard 0o644 mode."""
    file_path = Path(file_path)
    parent = file_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=parent,
        delete=False,
        encoding=encoding,
    ) as temp_file:
        temp_file.write(content)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_path = Path(temp_file.name)

    try:
        os.chmod(temp_path, 0o644)
    except OSError:
        pass

    os.replace(temp_path, file_path)


def atomic_write_json(file_path: Path, data: Any, indent: int = 2) -> None:
    """Atomically write JSON data to file with formatted indent."""
    content = json.dumps(data, indent=indent, ensure_ascii=False) + "\n"
    atomic_write_text(file_path, content)


def load_games(file_path: Path = GAMES_JSON_PATH) -> List[Dict[str, Any]]:
    """Load games dataset from JSON file."""
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_games_atomic(games: List[Dict[str, Any]], file_path: Path = GAMES_JSON_PATH) -> None:
    """Save games dataset atomically."""
    atomic_write_json(file_path, games)


def normalize_game_entry(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure standard keys and types exist for a game entry, preserving custom genres."""
    raw = raw or {}
    owner = str(raw.get("owner") or "").strip()
    repo = str(raw.get("repo") or "").strip()
    name = str(raw.get("name") or repo or "Unknown").strip()
    desc = str(raw.get("description") or "").strip()
    tech = str(raw.get("tech") or raw.get("language") or "Android").strip()

    # Trust explicit genre input if provided; otherwise infer from name + description
    raw_genre = raw.get("genre")
    if raw_genre and str(raw_genre).strip():
        genre = str(raw_genre).strip()
    else:
        genre = infer_genre(f"{name} {desc}")

    try:
        stars = int(raw.get("stars", 0))
    except (ValueError, TypeError):
        stars = 0

    return {
        "owner": owner,
        "repo": repo,
        "name": name,
        "description": desc,
        "genre": genre,
        "tech": tech,
        "stars": stars,
        "last_commit": str(raw.get("last_commit") or "N/A"),
        "license": str(raw.get("license") or "Unknown"),
        "default_branch": str(raw.get("default_branch") or "main"),
        "archived": bool(raw.get("archived", False)),
        "language": str(raw.get("language") or tech.split("/")[0].strip()),
    }
