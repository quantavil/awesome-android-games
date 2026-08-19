### Type of Change

Please check the option that best describes your PR:

- [ ] **Add a new game** (GitHub / GitLab / Codeberg)
- [ ] **Edit / Update existing game details** (Description, Tech stack, Genre categorization)
- [ ] **Remove a game** (Repository archived/deleted, non-game tool, quality/playability issues, author request)

---

### Game Details (if adding or editing)

- **Game Name**: 
- **Repository URL**: `https://...`
- **Host**: GitHub / GitLab / Codeberg / Other
- **Genre**: 
- **Tech Stack / Engine**: (e.g. Kotlin, LibGDX, Godot, Flutter, Unity)
- **License**: (e.g. MIT, GPL-3.0, Apache-2.0)

---

### Removal Reason (if requesting removal)

- **Reason**: 

---

### Contribution Checklist

- [ ] Repository is open-source under a recognized license.
- [ ] Game runs on / is buildable for Android.
- [ ] Verified game is functional and playable.
- [ ] `games.json` and `README.md` are in sync (`uv run python src/update_stats.py`).
- [ ] Ran automated tests and they pass: `uv run pytest`.
- [ ] Ran linter and it passes: `uv run ruff check .`.
