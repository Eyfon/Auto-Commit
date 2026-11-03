# Auto-Commit

[中文文档](README.md) · [MIT License](LICENSE)

Run a daily batch of **1–10 actual commits** in your own GitHub repository using
GitHub Actions. Default schedule: **09:17 Asia/Shanghai (01:17 UTC)**. No server,
always-on computer, or third-party Python packages required. GitHub may delay
scheduled runs.

The first successful write saves the day's randomly selected count. Repeated
runs skip completed days and resume partial batches. Every commit updates
`activity/daily.json`; commit dates are not backdated.

## Install with an AI assistant

Send this to an assistant with a terminal and GitHub access:

```text
Install https://github.com/Eyfon/Auto-Commit for me.
Read README.md and docs/AI-INSTALL.md and follow the installation and verification steps.
Use my currently authenticated GitHub account, create a new private independent
repository named daily-activity, and keep the default daily 09:17 Asia/Shanghai
schedule with a random batch of 1–10 commits.
```

You may need to complete GitHub's browser login yourself. Never paste a password
or token into chat. An assistant without execution access can only guide you.

## Install yourself

Requirements: Python 3.10+, Git, and [GitHub CLI](https://cli.github.com/).
Use `python3` or `py -3` if appropriate for your system.

```sh
gh auth login --hostname github.com
git clone https://github.com/Eyfon/Auto-Commit.git
cd Auto-Commit
python scripts/install.py --repository daily-activity
```

The installer creates a **private independent copy** from the GitHub template,
configures your commit identity using your account ID and noreply email, waits
for a read-only Actions check, then enables daily automation. It does not create
daily activity commits during installation. Subsequent runs use `GITHUB_TOKEN`;
no personal token is needed for the same repository.

Use `--dry-run` to preview, `--public` to create a public copy, or `--resume` to
finish a previous installation. Resume only accepts copies generated from this
template. It preserves content and visibility. If verification fails, the
repository is kept and automation stays disabled. Missing workflow scope can be
requested with `gh auth refresh --hostname github.com -s workflow`.

Alternatively, click **[Use this template](https://github.com/new?template_name=Auto-Commit&template_owner=Eyfon)**,
create a copy under your personal account, enable Actions if prompted, run
**Daily commit** with `verify_only` checked, and add the repository variable
`AUTO_COMMIT_ENABLED=true` after it succeeds. Independent template copies are
preferred because GitHub applies extra contribution restrictions to forks.

## Configuration

Repository variables live under **Settings → Secrets and variables → Actions → Variables**.

| Variable | Default |
| --- | --- |
| `AUTO_COMMIT_ENABLED` | unset / disabled; set exactly `true` to enable |
| `COMMIT_NAME`, `COMMIT_EMAIL` | personal repository owner's identity; set both or neither |
| `TARGET_REPOSITORY` | repository containing the workflow |
| `TARGET_BRANCH` | target repository's default branch |
| `COMMIT_FILE` | `activity/daily.json` |

Organization repositories require an explicit personal commit name and email.
Check your noreply address under GitHub Settings → Emails. To target a different
repository, set `TARGET_REPOSITORY` and store a fine-grained PAT with target
repository Contents read/write permission in the **secret** `TARGET_TOKEN`.
The target branch must already exist. Branch protection and organization policies
still apply; a read-only check does not prove write permission.

Edit `.github/workflows/daily-commit.yml` in your own copy's default branch to
change the UTC cron (`17 1 * * *`). Daily progress always uses UTC+8. View logs
under **Actions → Daily commit**. Manual runs default to read-only verification;
uncheck `verify_only` to execute a batch when enabled. Pause by setting
`AUTO_COMMIT_ENABLED=false` or disabling the workflow.

For private contribution display, enable **Profile → Contribution settings →
Private contributions**. Use an email associated with your account and a branch
that meets GitHub's contribution rules. Public heatmaps do not expose private
repository names or contents. Standard runner usage in private repositories
consumes your Actions allowance; check your GitHub plan. Public schedules may be
disabled after 60 days of inactivity.

See [configuration and troubleshooting](docs/CONFIGURATION.md),
[AI installation guide](docs/AI-INSTALL.md), and [development guide](CONTRIBUTING.md)
for details (Chinese). Template copies do not automatically receive upstream
updates. Keep your progress file and review upgrades before applying them.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests are offline. CI covers Ubuntu / Windows and Python 3.10 / 3.12.
Contribution counts are activity metrics, not a measure of meaningful work.
