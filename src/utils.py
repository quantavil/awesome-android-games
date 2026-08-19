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
    "Roguelike & Dungeon Crawler",
    "RPG & Adventure",
    "Sandbox & Simulation",
    "Board & Card Games",
    "Puzzle & Logic",
    "Word, Trivia & Educational",
    "Action & Arcade",
    "Platformer & Runner",
    "Racing & Sports",
    "Rhythm & Music",
    "Casual & Party",
]

# Mapping rules from keywords / topics to canonical genres (ordered by specificity)
GENRE_MAPPINGS: Dict[str, List[str]] = {
    "Strategy & 4X": [
        "mindustry",
        "unciv",
        "wesnoth",
        "vcmi",
        "freeciv",
        "settlers",
        "civilization",
        "4x",
        "strategy",
        "tower-defense",
        "tower defense",
        "tactics",
        "rts",
        "real-time strategy",
        "heroes of might",
        "anuto",
        "cpudefense",
        "latindefense",
        "liquid wars",
    ],
    "Roguelike & Dungeon Crawler": [
        "pixel dungeon",
        "dungeon crawl",
        "crawl",
        "roguelike",
        "hyperrogue",
        "cataclysm",
        "dungeon",
        "crawler",
        "rogue",
        "nethack",
        "angband",
        "cavern cravers",
    ],
    "RPG & Adventure": [
        "rpg",
        "stendhal",
        "flare",
        "easyrpg",
        "galgame",
        "visual novel",
        "idle fantasy",
        "role-playing",
        "quest",
        "adventure game",
        "interactive fiction",
        "open-adventure",
        "storygame",
        "narrative",
    ],
    "Sandbox & Simulation": [
        "voxel",
        "sandbox",
        "simulation",
        "simulator",
        "minetest",
        "luanti",
        "openttd",
        "freeminer",
        "principia",
        "endless sky",
        "simcity",
        "transport tycoon",
        "game of life",
        "space flight",
        "cuberite",
        "gravity",
    ],
    "Board & Card Games": [
        "chess",
        "lichess",
        "sanmill",
        "mill",
        "solitaire",
        "pysolfc",
        "card game",
        "card games",
        "cards",
        "board game",
        "board games",
        "gobandroid",
        "go game",
        "weiqi",
        "baduk",
        "blokus",
        "freebloks",
        "blokish",
        "ludo",
        "reversi",
        "othello",
        "checkers",
        "halma",
        "uno",
        "mahjong",
        "backgammon",
        "battleship",
        "dominoes",
        "tic tac toe",
        "tic-tac-toe",
        "dooz",
        "connect four",
        "draughts",
        "klondike",
        "tarock",
        "siete y media",
        "hearts and spades",
    ],
    "Word, Trivia & Educational": [
        "word",
        "trivia",
        "crossword",
        "anagram",
        "boggle",
        "scrabble",
        "quiz",
        "lexica",
        "ahorcado",
        "hangman",
        "unjumble",
        "wortmühle",
        "kanji",
        "filmfacts",
        "guess",
        "guesser",
        "parlera",
        "primary",
        "math trainer",
        "brain trainer",
    ],
    "Puzzle & Logic": [
        "puzzle",
        "sudoku",
        "minesweeper",
        "2048",
        "tatham",
        "rubik",
        "logic",
        "nonogram",
        "picross",
        "sokoban",
        "tangram",
        "jigsaw",
        "sliding puzzle",
        "15 puzzle",
        "flowit",
        "tessel",
        "water sort",
        "blockdrop",
        "block blast",
        "futoshiki",
        "zebra puzzle",
        "einstein",
        "match-3",
        "match 3",
        "dropcount",
        "drop7",
        "hue spill",
        "mastermind",
        "maze",
        "tangle",
        "knot",
        "pipe",
    ],
    "Rhythm & Music": [
        "rhythm",
        "piano",
        "pianoli",
        "singing",
        "music",
        "beat feet",
        "synth",
        "ultrastar",
        "hitster",
        "subster",
        "instrument",
    ],
    "Racing & Sports": [
        "supertuxkart",
        "kart",
        "racing",
        "race",
        "golf",
        "open-golf",
        "skiing",
        "snowboard",
        "sports",
        "football",
        "soccer",
        "hockey",
        "billiards",
        "pool game",
        "rally",
        "drift",
        "dexterity",
        "minigolf",
    ],
    "Platformer & Runner": [
        "platformer",
        "runner",
        "thextech",
        "mario",
        "aaaaxy",
        "pekka",
        "jump",
        "towerjumper",
        "flappy",
        "parkour",
        "side-scrolling",
        "sidescroller",
    ],
    "Action & Arcade": [
        "action",
        "arcade",
        "shooter",
        "doom",
        "quake",
        "idtech",
        "c-dogs",
        "arkanoid",
        "brick",
        "breakout",
        "pong",
        "space invader",
        "asteroids",
        "bullet hell",
        "shmup",
        "fighting",
        "beat em up",
        "king pong",
        "balloons",
        "dodge",
        "pinball",
        "retro arcade",
    ],
    "Casual & Party": [
        "casual",
        "party",
        "social deduction",
        "mafia",
        "mini-game",
        "minigame",
        "pet sim",
        "idle",
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
    """Infer canonical genre from title, description, or topics using word boundaries."""
    text_lower = text.lower()
    for genre, keywords in GENRE_MAPPINGS.items():
        for kw in keywords:
            # Word boundary matching for short terms / phrases to prevent false substring matches
            pattern = rf"\b{re.escape(kw)}\b"
            if re.search(pattern, text_lower):
                return genre
    return "Casual & Party"


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


def parse_repo_url(url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract owner, repo, and host from a Git repository URL (GitHub, GitLab, Codeberg).

    Supports:
    - https://github.com/owner/repo
    - https://gitlab.com/owner/repo
    - https://codeberg.org/owner/repo
    - git@github.com:owner/repo.git, git@gitlab.com:owner/repo.git, git@codeberg.org:owner/repo.git
    - owner/repo (defaults host to github.com)

    Returns:
        tuple (owner, repo, host) or (None, None, None)
    """
    if not url:
        return None, None, None

    clean = url.strip()

    # SSH pattern: git@<host>:<owner>/<repo>.git
    ssh_match = re.match(r"^git@([^:]+):([^/\s]+)/([^/\s#]+?)(?:\.git)?/?$", clean)
    if ssh_match:
        host = ssh_match.group(1).lower()
        owner = ssh_match.group(2)
        repo = ssh_match.group(3).removesuffix(".git")
        return owner, repo, host

    # HTTP/HTTPS URLs
    if clean.startswith("http://") or clean.startswith("https://"):
        parsed = urlparse(clean)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        # Filter out git branch/tree paths like /tree/main, /-/tree/master, /blob/
        raw_parts = [p for p in parsed.path.strip("/").split("/") if p]
        parts = []
        for p in raw_parts:
            if p in ("-", "tree", "blob", "src", "browse", "repository", "archive"):
                break
            parts.append(p)
        if len(parts) >= 2:
            owner = parts[0]
            repo = parts[1].removesuffix(".git")
            return owner, repo, netloc
        return None, None, None

    # Plain owner/repo format (allowing trailing slashes / .git)
    clean_slug = clean.strip("/")
    parts = [p for p in clean_slug.split("/") if p]
    if len(parts) == 2 and not clean.startswith("http"):
        return parts[0], parts[1].removesuffix(".git"), "github.com"

    return None, None, None


def parse_github_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract owner and repo name strictly from GitHub URL, SSH git path, or owner/repo string."""
    owner, repo, host = parse_repo_url(url)
    if host in ("github.com", "www.github.com"):
        return owner, repo
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
    """Ensure standard keys and types exist for a game entry, preserving custom genres and hosts."""
    raw = raw or {}
    owner = str(raw.get("owner") or "").strip()
    repo = str(raw.get("repo") or "").strip()
    host = str(raw.get("host") or "github.com").strip().lower()
    name = str(raw.get("name") or repo or "Unknown").strip()
    desc = re.sub(r"\s+", " ", str(raw.get("description") or "")).strip()
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

    entry: Dict[str, Any] = {
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
    if host and host != "github.com":
        entry["host"] = host
    elif "host" in raw and raw["host"]:
        entry["host"] = raw["host"]

    return entry
