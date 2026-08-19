# Contributing to Awesome Android Games

Thank you for your interest in contributing to **Awesome Android Games**! 🎉

## Submission Guidelines

Before submitting a new game, please ensure:

1. **Open-Source**: The repository must contain source code under an OSI-approved or recognized open-source license.
2. **Android Compatibility**: The game must run on or be buildable for Android devices (native Kotlin/Java, LibGDX, Godot Android, Flutter/Flame, Unity open-source, or C++ with NDK/SDL).
3. **Quality & Playability**: The game should be in a functional, playable state (not an abandoned empty template).

## Adding a Game

### Option 1: Using the `uv` updater CLI (Recommended)
```bash
uv run python src/update_stats.py --add "https://github.com/owner/repo" --desc "Brief 1-sentence description" --tech "Kotlin / LibGDX" --genre "Strategy & 4X"
```
This automatically formats and adds the game to `games.json`, fetches its live GitHub stats, and updates `README.md`.

### Option 2: Editing `games.json` directly
Add your entry into `games.json`:
```json
{
  "owner": "owner",
  "repo": "repo",
  "name": "Game Name",
  "description": "Brief 1-sentence description.",
  "genre": "Strategy & 4X",
  "tech": "Kotlin / LibGDX"
}
```
Then run:
```bash
uv run python src/update_stats.py
```

## Pull Request Process

1. Fork this repository.
2. Create a new branch: `git checkout -b add-game-name`.
3. Add the game following the steps above.
4. Verify tests pass: `uv run pytest`.
5. Commit your changes: `git commit -m "Add Game Name"`.
6. Push to your branch and open a Pull Request.
