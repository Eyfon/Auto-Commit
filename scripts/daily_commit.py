"""Create a saved daily batch of 1-10 commits, safely resuming partial runs."""

import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
import os
import re
import secrets
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
BEIJING = timezone(timedelta(hours=8))
MARKER = "github-daily-commit/v1"


def choose_daily_count():
    return secrets.randbelow(10) + 1


def resolve_author(api, source, name="", email=""):
    """Resolve the installer's configured identity or the source repository owner."""
    if bool(name) != bool(email):
        raise ValueError("Set both COMMIT_NAME and COMMIT_EMAIL, or leave both empty.")
    if name:
        return {"name": name, "email": email}
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source):
        raise ValueError("Set COMMIT_NAME and COMMIT_EMAIL, or SOURCE_REPOSITORY.")
    owner = source.split("/", 1)[0]
    user = api.request("GET", f"/users/{owner}")
    if user.get("type") != "User":
        raise ValueError("Organization repositories require COMMIT_NAME and COMMIT_EMAIL.")
    login = user["login"]
    return {"name": login, "email": f"{user['id']}+{login}@users.noreply.github.com"}


class APIError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"GitHub API returned HTTP {status}.")


class GitHub:
    def __init__(self, token):
        self.token = token

    def request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            API_ROOT + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "github-daily-commit",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            # Do not print request headers, tokens, or raw API responses.
            raise APIError(error.code) from None
        except (URLError, TimeoutError):
            raise RuntimeError("Cannot reach GitHub API; check connectivity and retry.") from None


def update(api, repository, branch, path, day, author=None, dry_run=False, choose_count=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("TARGET_REPOSITORY must be owner/repository.")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts) or "\\" in path:
        raise ValueError("COMMIT_FILE must be a repository-relative file path.")
    if parts[0].lower() in (".git", ".github"):
        raise ValueError("COMMIT_FILE must not point into .git or .github.")

    repo_path = f"/repos/{repository}"
    metadata = api.request("GET", repo_path)
    branch = branch or metadata["default_branch"]
    if not branch or branch.startswith("-"):
        raise ValueError("Invalid target branch.")
    # Fail clearly for empty repositories or nonexistent branches.
    api.request("GET", f"{repo_path}/branches/{quote(branch, safe='')}")
    file_path = f"{repo_path}/contents/{quote(path, safe='/')}"
    read_path = file_path + "?" + urlencode({"ref": branch})
    choose_count = choose_count or choose_daily_count
    planned_target = None
    commits_made = 0
    conflicts = 0
    # At most ten writes, plus bounded retries for conflicts with another writer.
    for _ in range(40):
        sha = None
        record = None
        try:
            existing = api.request("GET", read_path)
        except APIError as error:
            if error.status != 404:
                raise
        else:
            if not isinstance(existing, dict) or existing.get("type") != "file":
                raise ValueError("COMMIT_FILE points to something other than a regular file.")
            try:
                record = json.loads(base64.b64decode(existing["content"]))
            except (KeyError, ValueError, UnicodeError):
                raise ValueError("Refusing to overwrite an existing unmanaged file.") from None
            if not isinstance(record, dict) or record.get("generator") != MARKER:
                raise ValueError("Refusing to overwrite an existing unmanaged file.")
            previous_day = record.get("date")
            if not isinstance(previous_day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", previous_day):
                raise ValueError("Existing daily record contains an invalid date.")
            if previous_day > day:
                print(f"Skipped: {repository}@{branch} already records {previous_day}.")
                return commits_made
            sha = existing["sha"]

        if record is not None and record["date"] == day:
            if "target_commits" not in record and "completed_commits" not in record:
                print(f"Skipped: {day} already has a record from the previous version.")
                return commits_made
            target = record.get("target_commits")
            completed = record.get("completed_commits")
            if type(target) is not int or not 1 <= target <= 10:
                raise ValueError("Existing target_commits must be an integer from 1 to 10.")
            if type(completed) is not int or not 0 <= completed <= target:
                raise ValueError("Existing completed_commits is invalid.")
        else:
            if dry_run:
                print(f"Check passed: {repository}@{branch}:{path}; next batch will randomly choose 1-10 commits.")
                return 0
            if planned_target is None:
                planned_target = choose_count()
            target, completed = planned_target, 0
            if type(target) is not int or not 1 <= target <= 10:
                raise ValueError("Daily count must be an integer from 1 to 10.")

        if completed == target:
            print(f"Completed: {day} {completed}/{target}; no more commits needed.")
            return commits_made
        if dry_run:
            print(f"Check passed: {day} has {completed}/{target} commits; would resume {target - completed} remaining.")
            return 0

        content = json.dumps(
            {"generator": MARKER, "date": day, "timezone": "Asia/Shanghai",
             "target_commits": target, "completed_commits": completed + 1},
            ensure_ascii=False, indent=2,
        ) + "\n"
        payload = {
            "message": f"chore: daily activity {day} ({completed + 1}/{target})",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        if author:
            payload["author"] = author
            payload["committer"] = author
        try:
            result = api.request("PUT", file_path, payload)
        except APIError as error:
            conflicts += 1
            if error.status not in (409, 422) or conflicts >= 3:
                raise
            # Re-read both the saved random target and progress after a conflict.
            continue
        conflicts = 0
        commits_made += 1
        print(f"Committed {completed + 1}/{target}: {result['commit']['html_url']}")
    raise RuntimeError("Could not finish the daily batch within the retry limit.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Read GitHub state without writing")
    parser.add_argument("--check", action="store_true", help="Check repository access at any time, without writing")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    source = os.environ.get("SOURCE_REPOSITORY", "").strip()
    repository = os.environ.get("TARGET_REPOSITORY", source).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("TARGET_REPOSITORY must be owner/repository.")
    if not token:
        raise ValueError("Set GITHUB_TOKEN, or configure Actions secret TARGET_TOKEN.")
    if source and repository.lower() != source.lower() and os.environ.get("HAS_TARGET_TOKEN") == "false":
        raise ValueError("A different target repository requires Actions secret TARGET_TOKEN.")
    name = os.environ.get("COMMIT_NAME", "").strip()
    email = os.environ.get("COMMIT_EMAIL", "").strip()
    api = GitHub(token)
    author = resolve_author(api, source, name, email)
    print(f"Commit author: {author['name']} <{author['email']}>")
    update(
        api, repository,
        os.environ.get("TARGET_BRANCH", "").strip(),
        os.environ.get("COMMIT_FILE", "activity/daily.json").strip(),
        datetime.now(BEIJING).date().isoformat(),
        author=author, dry_run=args.dry_run or args.check,
    )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
