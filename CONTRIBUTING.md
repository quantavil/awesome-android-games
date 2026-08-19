# Contributing to Awesome Android Games

Thank you for your interest in contributing to **Awesome Android Games**! 🎉

We welcome submissions, metadata improvements, corrections, and removals to keep this catalog high-quality, comprehensive, and up-to-date.

---

## Table of Contents

- [Submission & Quality Guidelines](#submission--quality-guidelines)
- [Supported Git Forges](#supported-git-forges)
- [Adding a Game](#adding-a-game)
- [Editing or Updating a Game](#editing-or-updating-a-game)
- [Requesting a Game Removal](#requesting-a-game-removal)
- [Pull Request Process](#pull-request-process)
- [Automated Validation](#automated-validation)

---

## Submission & Quality Guidelines

Before submitting a game, please verify that it meets the following criteria:

1. **Open-Source**: The repository must contain source code under an OSI-approved or recognized open-source license (e.g. MIT, GPL, Apache, BSD, MPL, CC0).
2. **Android Compatible**: The game must run on or be buildable for Android devices (native Kotlin/Java, LibGDX, Godot Android, Flutter/Flame, Unity open-source, or C++ with NDK/SDL).
3. **Genuine Game**: The repository must be an actual playable video game or complete game engine (not a non-game tool, scorekeeper, calculator, companion wiki, or cheat utility).
4. **Quality & Playability**: The game should be functional and playable (not an empty boilerplate, 1-screen placeholder demo, or abandoned assignment).

---

## Supported Git Forges

The project natively tracks and fetches live statistics (stars, descriptions, last activity, licenses) from multiple Git hosts:

- **GitHub** (`github.com`)
- **GitLab** (`gitlab.com`, `invent.kde.org`, and self-hosted instances)
- **Codeberg & Forgejo / Gitea** (`codeberg.org`, `tea.codeberg.org`, and self-hosted instances)
- **SourceHut / Generic Git** (`git.sr.ht`, etc.)

---

## Adding a Game

### Option 1: CLI Auto-Fetch (Recommended)

You can pass a repository URL from any supported Git host. The updater will automatically extract the name, description, primary language, license, live star count, and infer the genre:

```bash
# GitHub
uv run python src/update_stats.py --add "https://github.com/owner/repo"

# GitLab
uv run python src/update_stats.py --add "https://gitlab.com/owner/repo"

# Codeberg
uv run python src/update_stats.py --add "https://codeberg.org/owner/repo"
```

> **Optional CLI Flags**: Override or specify metadata manually if desired:
> ```bash
> uv run python src/update_stats.py --add "https://gitlab.com/owner/repo" \
>   --name "My Awesome Game" \
>   --genre "Strategy & 4X" \
>   --tech "Kotlin / LibGDX" \
>   --desc "A tactical turn-based strategy game."
> ```

### Option 2: Editing `games.json` Directly

Add an entry to [`games.json`](games.json):

```json
{
  "owner": "owner",
  "repo": "repo",
  "name": "Game Name",
  "host": "gitlab.com",
  "genre": "Strategy & 4X",
  "tech": "Kotlin / LibGDX",
  "description": "A tactical turn-based strategy game."
}
```

*(Note: `"host"` defaults to `"github.com"` if omitted. For GitLab, Codeberg, or custom hosts, specify `"host"`).*

After updating `games.json`, run the sync script to update `README.md` and refresh stats:
```bash
uv run python src/update_stats.py
```

---

## Editing or Updating a Game

To edit or update existing game metadata (e.g. updating description, recategorizing genre, correcting engine/tech stack, or fixing URL):

1. Run the `--add` command with the same repository URL and the updated flags:
   ```bash
   uv run python src/update_stats.py --add "https://github.com/owner/repo" \
     --genre "Puzzle & Logic" \
     --tech "Godot / C#"
   ```
2. Or directly edit the matching item in [`games.json`](games.json), then run `uv run python src/update_stats.py`.

---

## Requesting a Game Removal

If a game should be removed from the list:

- **Reasons for removal**:
  - The repository has become proprietary, private, or deleted.
  - The project is an unplayable or abandoned minimal demo / assignment.
  - The entry is a non-game utility (tracker, companion app, calculator, scorekeeper).
  - Explicit removal request by the original repository owner/author.

- **How to request removal**:
  1. **Via Pull Request**: Remove the game object from [`games.json`](games.json), run `uv run python src/update_stats.py` to regenerate `README.md`, and submit a PR explaining the reason.
  2. **Via Issue**: Open an Issue on GitHub citing the game repository and the reason for removal.

---

## Pull Request Process

1. Fork this repository and clone your fork locally.
2. Create a feature branch:
   ```bash
   git checkout -b add-my-game
   ```
3. Make your changes in `games.json` or use `src/update_stats.py`.
4. Validate your changes:
   ```bash
   # Run automated test suite
   uv run pytest

   # Run linter
   uv run ruff check .
   ```
5. Commit your changes:
   ```bash
   git commit -m "Add/Update/Remove <Game Name>"
   ```
6. Push to your fork and open a Pull Request.

---

## Automated Validation

Every Pull Request automatically runs CI checks to ensure:
- JSON schema validity and deduplication in `games.json`.
- Markdown link and Table of Contents synchronization with `README.md`.
- Accurate multi-forge repository parsing across GitHub, GitLab, and Codeberg.
- Code style and lint passing with zero errors (`ruff check`).
