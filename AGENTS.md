# Agent guidance

For an installation request, read `README.md` and `docs/AI-INSTALL.md`, then use
`scripts/install.py`. Defaults are a new private personal repository, daily at
09:17 Asia/Shanghai, and a random batch of 1–10 commits. Respect the user's
explicit repository, privacy and schedule preferences.

For development, read `CONTRIBUTING.md`. Run
`python -m unittest discover -s tests -v` after code changes. Keep both README
files and installation/configuration docs consistent with behavior.

Do not hardcode the template author's commit identity into generated copies.
Keep the template inactive by default. Resolve credentials through GitHub CLI
or Actions environment variables, and never print or commit tokens.
