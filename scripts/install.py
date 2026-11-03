"""Install Auto-Commit into a new personal GitHub repository using GitHub CLI."""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time


TEMPLATE = "Eyfon/Auto-Commit"
WORKFLOW = "daily-commit.yml"
REPOSITORY_PATTERN = r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"


class CLIError(RuntimeError):
    pass


class GitHubCLI:
    def __init__(self):
        self.executable = shutil.which("gh")
        if not self.executable:
            raise CLIError("Install GitHub CLI (https://cli.github.com), then run gh auth login.")

    def run(self, arguments, payload=None):
        result = subprocess.run(
            [self.executable, *arguments],
            input=None if payload is None else json.dumps(payload),
            capture_output=True, text=True, encoding="utf-8",
            timeout=90, check=False,
        )
        if result.returncode:
            raise CLIError(result.stderr.strip() or "GitHub CLI failed. Run gh auth status.")
        return result.stdout

    def api(self, path, method="GET", payload=None):
        arguments = ["api", "--hostname", "github.com", path, "--method", method]
        if payload is not None:
            arguments += ["--input", "-"]
        output = self.run(arguments, payload)
        return json.loads(output) if output.strip() else None

    def variable(self, repository, name, value):
        self.run(["variable", "set", name, "--repo", f"github.com/{repository}", "--body", value])


def repository_name(value, login):
    repository = value if "/" in value else f"{login}/{value}"
    if not re.fullmatch(REPOSITORY_PATTERN, repository):
        raise ValueError("Repository must be NAME or YOUR_USERNAME/NAME.")
    owner, name = repository.split("/")
    if name in (".", "..") or name.startswith("-") or owner.lower() != login.lower():
        raise ValueError("Choose a repository in the authenticated user's personal account.")
    if repository.lower() == TEMPLATE.lower():
        raise ValueError("Choose a new repository name, different from the upstream template.")
    return f"{login}/{name}"


def wait_for_workflow(cli, repository, timeout=90):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return cli.api(f"repos/{repository}/actions/workflows/{WORKFLOW}")
        except CLIError as error:
            if "404" not in str(error) or time.monotonic() >= deadline:
                raise
            time.sleep(3)


def verify_installation(cli, repository, branch, timeout=300):
    """Dispatch a check and wait for this dispatch, ignoring older run results."""
    runs_path = f"repos/{repository}/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=30"
    previous = {run["id"] for run in cli.api(runs_path)["workflow_runs"]}
    cli.api(f"repos/{repository}/actions/workflows/{WORKFLOW}/dispatches", "POST",
            {"ref": branch, "inputs": {"verify_only": "true"}})
    deadline = time.monotonic() + timeout
    run_id = None
    while time.monotonic() < deadline:
        if run_id is None:
            candidates = [run for run in cli.api(runs_path)["workflow_runs"]
                          if run["id"] not in previous and run["head_branch"] == branch]
            if candidates:
                run_id = min(candidates, key=lambda run: run["id"])["id"]
                print(f"Checking: https://github.com/{repository}/actions/runs/{run_id}", flush=True)
        if run_id is not None:
            run = cli.api(f"repos/{repository}/actions/runs/{run_id}")
            if run["status"] == "completed":
                if run["conclusion"] != "success":
                    raise CLIError(f"Verification failed ({run['conclusion']}): {run['html_url']}")
                # A successful workflow whose only job was skipped is not verification.
                jobs = cli.api(f"repos/{repository}/actions/runs/{run_id}/jobs")["jobs"]
                if not any(job["name"] == "commit" and job["conclusion"] == "success" for job in jobs):
                    raise CLIError(f"Verification job did not run: {run['html_url']}")
                return run["html_url"]
        time.sleep(5)
    raise CLIError("Verification timed out; check Actions, then rerun this command with --resume.")


def install(cli, requested_repository, public=False, resume=False, dry_run=False):
    user = cli.api("user")
    repository = repository_name(requested_repository, user["login"])
    email = f"{user['id']}+{user['login']}@users.noreply.github.com"
    existing = None
    try:
        existing = cli.api(f"repos/{repository}")
    except CLIError as error:
        if "404" not in str(error):
            raise
    if existing:
        template = (existing.get("template_repository") or {}).get("full_name", "")
        if not resume:
            raise ValueError("Repository already exists. Use a new name, or --resume for a previous installation.")
        if existing.get("fork") or template.lower() != TEMPLATE.lower():
            raise ValueError("--resume only accepts an independent repository created from this template.")
    elif resume:
        raise ValueError("Repository does not exist. Omit --resume to create it.")
    print(f"Repository: https://github.com/{repository}", flush=True)
    print(f"Commit author: {user['login']} <{email}>", flush=True)
    visibility = ("private" if existing["private"] else "public") if existing else ("public" if public else "private")
    print(f"Visibility: {visibility}; schedule: 09:17 Asia/Shanghai; daily commits: 1-10.", flush=True)
    if dry_run:
        print("Preview only: no repository, variables, workflows or commits were changed.")
        return repository
    if not existing:
        owner, name = repository.split("/")
        print("Creating repository from template...", flush=True)
        existing = cli.api(f"repos/{TEMPLATE}/generate", "POST", {
            "owner": owner, "name": name, "private": not public,
            "description": "Daily GitHub commits powered by Eyfon/Auto-Commit",
            "include_all_branches": False,
        })
    # Keep automation inactive if installation or verification fails midway.
    cli.variable(repository, "AUTO_COMMIT_ENABLED", "false")
    cli.variable(repository, "COMMIT_NAME", user["login"])
    cli.variable(repository, "COMMIT_EMAIL", email)
    print("Waiting for GitHub to register the workflow...", flush=True)
    wait_for_workflow(cli, repository)
    cli.api(f"repos/{repository}/actions/workflows/{WORKFLOW}/enable", "PUT")
    print("Running read-only verification (this may take several minutes)...", flush=True)
    url = verify_installation(cli, repository, existing["default_branch"])
    cli.variable(repository, "AUTO_COMMIT_ENABLED", "true")
    print(f"Installed and enabled. Verification: {url}", flush=True)
    print("The first batch will run on the next schedule; no activity commits were created by installation.")
    return repository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="New personal repository: NAME or YOUR_USERNAME/NAME")
    parser.add_argument("--public", action="store_true", help="Create public repository (default: private)")
    parser.add_argument("--resume", action="store_true", help="Finish setup in an existing copy made from this template")
    parser.add_argument("--dry-run", action="store_true", help="Preview installation without changing GitHub")
    args = parser.parse_args()
    install(GitHubCLI(), args.repository, public=args.public, resume=args.resume, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Error: {error}", file=sys.stderr)
        print("If a repository was created, it is kept. Fix the issue and retry with --resume.", file=sys.stderr)
        sys.exit(1)
