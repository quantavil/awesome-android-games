"""Shared utilities for Awesome Android Games.

Provides atomic file IO, robust GitHub URL parsing, API authentication,
star formatting, GFM slug generation, and dataset normalization.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
GAMES_JSON_PATH = ROOT_DIR / "games.json"
README_PATH = ROOT_DIR / "README.md"

# Description written by add_game when the submitter gave none; replaced by live data later.
PLACEHOLDER_DESCRIPTION = "Open-source Android game."

# Hosts whose stats can be fetched live, keyed by the API flavour they speak.
GITLAB_HOSTS = frozenset({"invent.kde.org", "gitlab.wikimedia.org"})
FORGEJO_HOSTS = frozenset(
    {"teapot.informationsanarchistik.de", "git.justquitstudios.de", "git.harrault.fr"}
)


def forge_kind(host: str) -> str:
    """Classify a host as 'github', 'gitlab', 'forgejo' (Codeberg/Gitea family) or 'other'."""
    h = (host or "").lower()
    if h in ("github.com", "www.github.com"):
        return "github"
    if "gitlab" in h or h in GITLAB_HOSTS:
        return "gitlab"
    if "codeberg" in h or h in FORGEJO_HOSTS:
        return "forgejo"
    return "other"


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


def escape_markdown_text(text: str) -> str:
    """Make free text safe inside a Markdown link label or bullet line.

    Brackets are escaped so they cannot close a link early. Angle brackets become HTML
    entities so issue-supplied text cannot inject comments or tags, such as a fake
    GAMES_LIST_END marker that would break README regeneration.
    """
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("[", "\\[").replace("]", "\\]")


# (SPDX id, markers that must all appear, markers that must not appear). Lowercase, with
# whitespace collapsed before matching, so line wrapping and capitalisation do not matter.
_LICENSE_SIGNATURES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("AGPL-3.0", ("gnu affero general public license", "version 3"), ()),
    ("LGPL-3.0", ("gnu lesser general public license", "version 3"), ()),
    ("LGPL-2.1", ("gnu lesser general public license", "version 2.1"), ()),
    ("GPL-3.0", ("gnu general public license", "version 3"), ("gnu lesser", "gnu affero")),
    ("GPL-2.0", ("gnu general public license", "version 2"), ("gnu lesser", "gnu affero")),
    ("Apache-2.0", ("apache license", "version 2.0"), ()),
    ("MPL-2.0", ("mozilla public license version 2.0",), ()),
    ("Unlicense", ("this is free and unencumbered software",), ()),
    ("MIT", ("permission is hereby granted, free of charge",), ()),
    (
        "BSD-3-Clause",
        ("redistribution and use in source and binary forms", "neither the name of"),
        (),
    ),
    (
        "BSD-2-Clause",
        ("redistribution and use in source and binary forms",),
        ("neither the name of",),
    ),
    ("Zlib", ("altered source versions must be plainly marked",), ()),
)


def detect_license_from_text(text: str) -> Optional[str]:
    """Identify a single open-source license from LICENSE file text.

    Returns None when no known license matches, or when the file matches more than one
    (for example an Apache notice for bundled assets next to the code license). Callers
    should treat None as "unknown" rather than guessing.
    """
    flat = " ".join(text.lower().split())
    matches = {
        spdx
        for spdx, required, forbidden in _LICENSE_SIGNATURES
        if all(marker in flat for marker in required)
        and not any(marker in flat for marker in forbidden)
    }
    return matches.pop() if len(matches) == 1 else None


def is_same_game(entry: Dict[str, Any], host: str, owner: str, repo: str) -> bool:
    """Case-insensitive match of a catalog entry against host, owner and repo."""
    return (
        str(entry.get("host", "github.com")).lower() == host.lower()
        and str(entry.get("owner", "")).lower() == owner.lower()
        and str(entry.get("repo", "")).lower() == repo.lower()
    )


def find_game_index(games: List[Dict[str, Any]], host: str, owner: str, repo: str) -> Optional[int]:
    """Return the index of the first matching catalog entry, or None."""
    for index, entry in enumerate(games):
        if is_same_game(entry, host, owner, repo):
            return index
    return None


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


_PATH_STOP_SEGMENTS = frozenset({"-", "tree", "blob", "src", "browse", "repository", "archive"})


def _split_owner_repo(host: str, path: str) -> tuple[Optional[str], Optional[str]]:
    """Split a URL path into (owner, repo).

    GitLab supports nested groups, so there the owner is everything before the last
    segment. GitHub, Codeberg and other hosts use the first two segments.
    Branch and page markers such as /tree/main or /-/issues end the path.
    """
    parts: list[str] = []
    for segment in (p for p in path.strip("/").split("/") if p):
        if segment in _PATH_STOP_SEGMENTS:
            break
        parts.append(segment)
    if len(parts) < 2:
        return None, None
    if forge_kind(host) == "gitlab":
        owner, repo = "/".join(parts[:-1]), parts[-1]
    else:
        owner, repo = parts[0], parts[1]
    repo = repo.removesuffix(".git")
    return (owner, repo) if owner and repo else (None, None)


def parse_repo_url(url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract owner, repo, and host from a Git repository URL (GitHub, GitLab, Codeberg).

    Supports:
    - https://github.com/owner/repo (also http://, ssh://, and scheme-less github.com/owner/repo)
    - https://gitlab.com/group/subgroup/repo (nested GitLab groups)
    - git@github.com:owner/repo.git (scp-style SSH, any host)
    - owner/repo (defaults host to github.com)

    Returns:
        tuple (owner, repo, host) or (None, None, None)
    """
    if not url:
        return None, None, None

    clean = url.strip()

    # scp-style SSH: git@<host>:<path>
    ssh_match = re.match(r"^git@([^:/]+):(.+)$", clean)
    if ssh_match:
        host, path = ssh_match.group(1).lower(), ssh_match.group(2)
    elif clean.startswith(("http://", "https://", "ssh://")):
        parsed = urlparse(clean)
        host, path = (parsed.hostname or "").lower(), parsed.path
    elif re.match(r"^[\w.-]+\.[a-z]{2,}/[^/]+/[^/]+", clean, re.IGNORECASE):
        # Scheme-less URL such as github.com/owner/repo
        parsed = urlparse(f"https://{clean}")
        host, path = (parsed.hostname or "").lower(), parsed.path
    else:
        # Plain owner/repo (trailing slashes and .git allowed), defaulting to GitHub
        parts = [p for p in clean.strip("/").split("/") if p]
        if len(parts) == 2 and ":" not in clean:
            return parts[0], parts[1].removesuffix(".git"), "github.com"
        return None, None, None

    if host.startswith("www."):
        host = host[4:]
    if not host:
        return None, None, None
    owner, repo = _split_owner_repo(host, path)
    if not owner or not repo:
        return None, None, None
    return owner, repo, host


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
    """Atomically write text to a file via a temp file in the same directory.

    An existing target keeps its permission bits; a new file gets 0o644. The temp file
    is removed if anything fails before the final replace.
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(file_path.stat().st_mode) if file_path.exists() else 0o644

    fd, temp_name = tempfile.mkstemp(
        dir=file_path.parent, prefix=f".{file_path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        try:
            os.chmod(temp_name, mode)
        except OSError:
            pass
        os.replace(temp_name, file_path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


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

    # Keep an explicit genre. When it is unknown, leave it empty: inferring from the
    # placeholder description would misfile games, and the stats pass infers it from
    # real repository data (description and topics) instead.
    genre = str(raw.get("genre") or "").strip()

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
