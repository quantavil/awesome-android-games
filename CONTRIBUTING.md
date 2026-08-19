# Contributing to Awesome Android Games

Thank you for your interest in contributing to **Awesome Android Games**! 🎉

## Submission Guidelines

Before submitting a new game, please ensure:

1. **Open-Source**: The repository must contain source code under an OSI-approved or recognized open-source license.
2. **Android Compatibility**: The game must run on or be buildable for Android devices (native Kotlin/Java, LibGDX, Godot Android, Flutter/Flame, Unity open-source, or C++ with NDK/SDL).
3. **Quality & Playability**: The game should be in a functional, playable state (not an abandoned empty template).

## Adding a Game

### Option 1: 1-Command Auto-Fetch (Easiest)
Simply provide the GitHub repository URL. The tool automatically extracts the name, description, primary language, license, stars, and infers the category:
```bash
uv run python src/update_stats.py --add "https://github.com/owner/repo"
```
*(Optional flags `--desc`, `--tech`, `--genre` can be passed if you wish to override auto-detected metadata).*

### Option 2: Editing `games.json` directly
Append your entry to `games.json`:
```json
{
  "owner": "owner",
  "repo": "repo"
}
```
Then run:
```bash
uv run python src/update_stats.py
```
The updater will automatically fill in the stars, description, tech stack, and update `README.md`.

## Pull Request Process

1. Fork this repository.
2. Create a new branch: `git checkout -b add-game-name`.
3. Add the game following the steps above.
4. Verify tests pass: `uv run pytest`.
5. Commit your changes: `git commit -m "Add Game Name"`.
6. Push to your branch and open a Pull Request.
