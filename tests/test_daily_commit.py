import base64
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    "daily_commit", Path(__file__).resolve().parents[1] / "scripts" / "daily_commit.py"
)
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)
DAY = "2026-11-04"


def record(target=3, completed=1, day=DAY):
    return {"generator": daily.MARKER, "date": day, "timezone": "Asia/Shanghai",
            "target_commits": target, "completed_commits": completed}


class FakeGitHub:
    """A contents-API fake that persists progress and enforces file SHA leases."""
    def __init__(self, initial=None):
        self.record = initial
        self.sha = "initial" if initial is not None else None
        self.writes = []
        self.calls = []
        self.on_put = None

    def request(self, method, path, payload=None):
        self.calls.append((method, path))
        if method == "GET" and path == "/repos/owner/target":
            return {"default_branch": "main"}
        if method == "GET" and "/branches/" in path:
            return {"name": "main"}
        if method == "GET":
            if self.record is None:
                raise daily.APIError(404)
            return {"type": "file", "sha": self.sha,
                    "content": base64.b64encode(json.dumps(self.record).encode()).decode()}
        if self.on_put:
            self.on_put(payload)
        if payload.get("sha") != self.sha:
            raise daily.APIError(409)
        self.record = json.loads(base64.b64decode(payload["content"]))
        self.writes.append(copy.deepcopy(payload))
        self.sha = f"version-{len(self.writes)}"
        return {"commit": {"html_url": f"https://github.com/example/commit/{self.sha}"}}


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def update(self, api, **kwargs):
        return daily.update(api, "owner/target", kwargs.pop("branch", ""),
                            kwargs.pop("path", "activity/daily.json"), DAY, **kwargs)

    def test_each_possible_count_creates_exactly_that_many_commits(self):
        for count in range(1, 11):
            with self.subTest(count=count):
                api = FakeGitHub()
                choose = Mock(return_value=count)
                self.assertEqual(self.update(api, choose_count=choose), count)
                choose.assert_called_once_with()
                self.assertEqual(len(api.writes), count)
                self.assertEqual(api.record, record(count, count))
                for index, payload in enumerate(api.writes, 1):
                    self.assertEqual(payload["message"], f"chore: daily activity {DAY} ({index}/{count})")

    def test_completed_day_never_rerolls_or_adds_commits(self):
        api = FakeGitHub(record(7, 7))
        choose = Mock(side_effect=AssertionError("must not reroll"))
        self.assertEqual(self.update(api, choose_count=choose), 0)
        self.assertEqual(api.writes, [])
        choose.assert_not_called()

    def test_partial_batch_resumes_saved_target(self):
        api = FakeGitHub(record(8, 3))
        choose = Mock(side_effect=AssertionError("must not reroll"))
        self.assertEqual(self.update(api, choose_count=choose), 5)
        self.assertEqual(api.record, record(8, 8))
        choose.assert_not_called()

    def test_interrupted_run_can_resume_without_exceeding_target(self):
        api = FakeGitHub()
        def fail_second_write(payload):
            if len(api.writes) == 1:
                raise daily.APIError(500)
        api.on_put = fail_second_write
        with self.assertRaises(daily.APIError):
            self.update(api, choose_count=lambda: 4)
        self.assertEqual(api.record, record(4, 1))
        api.on_put = None
        self.assertEqual(self.update(api, choose_count=Mock(side_effect=AssertionError)), 3)
        self.assertEqual(len(api.writes), 4)
        self.assertEqual(api.record, record(4, 4))

    def test_next_day_selects_new_count(self):
        api = FakeGitHub(record(10, 10, "2026-11-03"))
        choose = Mock(return_value=2)
        self.assertEqual(self.update(api, choose_count=choose), 2)
        self.assertEqual(api.record, record(2, 2))
        self.assertEqual(api.writes[0]["sha"], "initial")

    def test_conflict_adopts_other_writers_saved_target(self):
        for status in (409, 422):
            with self.subTest(status=status):
                api = FakeGitHub()
                def other_writer(payload):
                    api.record, api.sha = record(2, 1), "other-writer"
                    api.on_put = None
                    raise daily.APIError(status)
                api.on_put = other_writer
                self.assertEqual(self.update(api, choose_count=lambda: 10), 1)
                self.assertEqual(api.record, record(2, 2))

    def test_three_consecutive_conflicts_fail_without_unbounded_retries(self):
        api = FakeGitHub()
        attempts = Mock(side_effect=daily.APIError(409))
        api.on_put = attempts
        with self.assertRaises(daily.APIError):
            self.update(api, choose_count=lambda: 3)
        self.assertEqual(attempts.call_count, 3)
        self.assertEqual(api.writes, [])

    def test_check_does_not_write_or_choose_a_count(self):
        for initial in (None, record(4, 2), record(4, 4), record(day="2026-11-03")):
            with self.subTest(initial=initial):
                api = FakeGitHub(initial)
                choose = Mock(side_effect=AssertionError)
                self.assertEqual(self.update(api, dry_run=True, choose_count=choose), 0)
                self.assertEqual(api.writes, [])
                choose.assert_not_called()

    def test_legacy_same_day_is_already_complete(self):
        for periods in (None, ["morning"], ["morning", "afternoon"]):
            initial = {"generator": daily.MARKER, "date": DAY}
            if periods is not None:
                initial["completed_periods"] = periods
            api = FakeGitHub(initial)
            self.assertEqual(self.update(api), 0)
            self.assertEqual(api.writes, [])

    def test_future_record_is_not_overwritten(self):
        api = FakeGitHub(record(day="2026-11-05"))
        self.assertEqual(self.update(api), 0)
        self.assertEqual(api.writes, [])

    def test_unmanaged_content_is_preserved(self):
        for initial in ({"generator": "other-tool", "date": DAY}, [1, 2], "text"):
            with self.subTest(initial=initial):
                api = FakeGitHub(initial)
                with self.assertRaisesRegex(ValueError, "unmanaged"):
                    self.update(api)
                self.assertEqual(api.writes, [])

    def test_invalid_progress_is_rejected(self):
        for target, completed in ((0, 0), (11, 1), (True, 0), (3, -1), (3, 4), (3, True), (None, 1)):
            with self.subTest(target=target, completed=completed):
                api = FakeGitHub(record(target, completed))
                with self.assertRaises(ValueError):
                    self.update(api)
                self.assertEqual(api.writes, [])

    def test_invalid_random_count_is_rejected(self):
        for count in (0, 11, True, "3"):
            api = FakeGitHub()
            with self.assertRaises(ValueError):
                self.update(api, choose_count=lambda: count)
            self.assertEqual(api.writes, [])

    def test_author_is_applied_to_every_commit(self):
        api = FakeGitHub()
        author = {"name": "octocat", "email": "12345+octocat@users.noreply.github.com"}
        self.update(api, author=author, choose_count=lambda: 2)
        for payload in api.writes:
            self.assertEqual(payload["author"], author)
            self.assertEqual(payload["committer"], author)

    def test_branch_slashes_are_encoded(self):
        api = FakeGitHub(record(1, 1))
        self.update(api, branch="automation/daily")
        self.assertIn("automation%2Fdaily", api.calls[1][1])
        self.assertIn("ref=automation%2Fdaily", api.calls[2][1])

    def test_permission_error_is_not_treated_as_missing_file(self):
        api = Mock()
        api.request.side_effect = [{"default_branch": "main"}, {}, daily.APIError(403)]
        with self.assertRaises(daily.APIError):
            self.update(api)
        self.assertEqual(api.request.call_count, 3)

    def test_invalid_paths_fail_before_network_access(self):
        for path in ("../README.md", "/README.md", ".github/workflows/x.yml", "a\\b", "a//b"):
            api = Mock()
            with self.assertRaises(ValueError):
                self.update(api, path=path)
            api.request.assert_not_called()

    def test_directory_is_not_overwritten(self):
        api = Mock()
        api.request.side_effect = [{"default_branch": "main"}, {}, []]
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.update(api)
        self.assertEqual(api.request.call_count, 3)

    def test_random_count_includes_both_endpoints(self):
        for raw in range(10):
            with patch.object(daily.secrets, "randbelow", return_value=raw) as random:
                self.assertEqual(daily.choose_daily_count(), raw + 1)
                random.assert_called_once_with(10)


class AuthorTests(unittest.TestCase):
    def test_owner_identity_does_not_use_template_author(self):
        api = Mock()
        api.request.return_value = {"type": "User", "login": "octocat", "id": 12345}
        self.assertEqual(daily.resolve_author(api, "octocat/activity"),
                         {"name": "octocat", "email": "12345+octocat@users.noreply.github.com"})
        api.request.assert_called_once_with("GET", "/users/octocat")

    def test_explicit_verified_identity_is_preserved(self):
        api = Mock()
        self.assertEqual(daily.resolve_author(api, "company/activity", "Alice", "alice@example.com"),
                         {"name": "Alice", "email": "alice@example.com"})
        api.request.assert_not_called()

    def test_partial_identity_and_missing_source_are_rejected(self):
        for source, name, email in (("", "", ""), ("a/b", "Alice", ""), ("a/b", "", "a@b.c")):
            api = Mock()
            with self.assertRaises(ValueError):
                daily.resolve_author(api, source, name, email)
            api.request.assert_not_called()

    def test_organization_requires_a_personal_identity(self):
        api = Mock()
        api.request.return_value = {"type": "Organization", "login": "company", "id": 123}
        with self.assertRaisesRegex(ValueError, "Organization"):
            daily.resolve_author(api, "company/activity")


if __name__ == "__main__":
    unittest.main()
