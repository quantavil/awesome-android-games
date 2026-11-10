# Contributing to Awesome Android Games

Thank you for your interest in contributing to **Awesome Android Games**! 🎉

We welcome submissions, metadata improvements, corrections, and removals to keep this catalog high-quality, comprehensive, and up-to-date.

---

## Table of Contents

- [Submission & Quality Guidelines](#submission--quality-guidelines)
- [Supported Git Forges](#supported-git-forges)
- [How to Contribute](#how-to-contribute)
  - [Pathway A: GitHub Issues (Easiest)](#pathway-a-github-issues-easiest)
  - [Pathway B: Pull Requests (Fast-Tracked)](#pathway-b-pull-requests-fast-tracked)
- [CLI Tools & Commands](#cli-tools--commands)
  - [Adding / Updating Games](#adding--updating-games)
  - [Removing Games](#removing-games)
- [Maintainer IssueOps Automation](#maintainer-issueops-automation)
- [Automated Validation & CI](#automated-validation--ci)

---

## Submission & Quality Guidelines

Before submitting a game, please verify that it meets the following criteria:

1. **Open-Source**: The repository must contain source code under an OSI-approved or recognized open-source license (e.g. MIT, GPL, Apache, BSD, MPL, CC0).
2. **Android Compatible**: The game must run on or be buildable for Android devices (native Kotlin/Java, LibGDX, Godot Android, Flutter/Flame, Unity open-source, or C++ with NDK/SDL).
3. **Genuine Game**: The repository must be an actual playable video game or complete game engine (not a non-game tool, scorekeeper, calculator, companion wiki, or cheat utility).
4. **Quality & Playability**: The game should be functional and playable (not an empty boilerplate, 1-screen placeholder demo, or abandoned assignment).

---

## Supported Git Forges

Any public Git repository can be submitted, but live statistics (stars, description, last activity, license) are fetched only from these hosts:

- **GitHub** (`github.com`)
- **GitLab** (`gitlab.com`, `invent.kde.org`, `gitlab.wikimedia.org`, and any host whose name contains `gitlab`)
- **Codeberg & Forgejo / Gitea** (`codeberg.org`, `tea.codeberg.org`, and the self-hosted instances listed in `src/utils.py`)

Other hosts, such as SourceHut (`git.sr.ht`), are accepted, but their stats are not refreshed automatically. Those entries keep the values they were added with.

---

## How to Contribute

### Pathway A: GitHub Issues (Easiest)

No local setup or programming required! You can use our structured issue templates:

- **[Suggest a New Game](https://github.com/quantavil/awesome-android-games/issues/new?template=add-game.yml)**: Provide the repository URL, engine/tech stack, and game details.
- **[Update Game Metadata](https://github.com/quantavil/awesome-android-games/issues/new?template=update-game.yml)**: Fix descriptions, recategorize genres, or update URLs. A maintainer applies `approved-add` to the request, which updates the existing entry in place.
- **[Request Game Removal](https://github.com/quantavil/awesome-android-games/issues/new?template=remove-game.yml)**: Report defunct, closed-source, or unplayable entries.

### Pathway B: Pull Requests (Fast-Tracked)

If you'd like your changes merged directly:

1. Fork this repository and clone locally.
2. Create a branch (`git checkout -b add-my-game`).
3. Use the CLI tool (below) or edit [`games.json`](games.json), then run `uv run python src/update_stats.py` so `README.md` matches.
4. Run the checks: `uv run pytest`, `uv run ruff check .`, and `uv run ruff format --check .`.
5. Commit as `Add/Update/Remove <Game Name>` and open a Pull Request.

---

## CLI Tools & Commands

### Adding / Updating Games

You can pass a repository URL from any supported Git host. The updater will automatically extract the name, description, primary language, license, live star count, and infer the genre:

```bash
# Auto-fetch metadata and add/update game
uv run python src/update_stats.py --add "https://github.com/owner/repo"

# Optional overrides
uv run python src/update_stats.py --add "https://gitlab.com/owner/repo" \
  --name "My Awesome Game" \
  --genre "Strategy & 4X" \
  --tech "Kotlin / LibGDX" \
  --desc "A tactical turn-based strategy game."
```

### Removing Games

To remove a game from the dataset and regenerate the list:

```bash
# Remove by repository URL or slug
uv run python src/update_stats.py --remove "https://github.com/owner/repo"
```

---

## Maintainer IssueOps Automation

Maintainers can automatically process community issues using GitHub Actions IssueOps:

### Comment Commands
Comment directly on any submission issue:
- `/add` — Adds the game using the issue form's repository URL and metadata.
- `/add <url> [--genre <genre>] [--tech <tech>]` — Adds a game with explicit parameters. If the game is already listed, its details are updated in place.
- `/remove` — Removes the game cited in the removal request issue.
- `/remove <url>` — Removes a specific game URL.

### Label Triggers
Applying the following labels will automatically execute the action, sync `README.md`, run tests, commit to `main`, and close the issue:
- `approved-add`
- `approved-remove`

---

## Automated Validation & CI

Every Pull Request and IssueOps run automatically executes CI checks:
- JSON schema validity and deduplication in `games.json`.
- Markdown link and Table of Contents synchronization with `README.md`.
- Accurate multi-forge repository parsing across GitHub, GitLab, and Codeberg.
- Lint passing with zero errors (`ruff check`) and formatting clean (`ruff format --check`).
- Full pytest test suite execution.
- Workflow runs that update the catalog share one queue, so two runs never rewrite `games.json` at the same time.
