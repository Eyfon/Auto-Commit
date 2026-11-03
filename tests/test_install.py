import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    "install", Path(__file__).resolve().parents[1] / "scripts" / "install.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
REPO = "octocat/daily-activity"


class FakeCLI:
    def __init__(self, existing=None):
        self.existing = existing
        self.calls = []
        self.variables = {}

    def api(self, path, method="GET", payload=None):
        self.calls.append((path, method, payload))
        if path == "user":
            return {"login": "octocat", "id": 12345}
        if path == f"repos/{REPO}":
            if self.existing is None:
                raise installer.CLIError("Not Found (HTTP 404)")
            return self.existing
        if path.endswith("/generate"):
            return {"default_branch": "main", "private": payload["private"]}
        if path.endswith("daily-commit.yml"):
            return {"id": 10}
        if path.endswith("/enable"):
            return None
        raise AssertionError(path)

    def variable(self, repository, name, value):
        self.calls.append((repository, name, value))
        self.variables[name] = value


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_creates_private_independent_copy_and_activates_after_check(self):
        cli = FakeCLI()
        def verify(*args):
            self.assertEqual(cli.variables["AUTO_COMMIT_ENABLED"], "false")
            return "https://example.com/check"
        with patch.object(installer, "verify_installation", side_effect=verify) as check:
            self.assertEqual(installer.install(cli, "daily-activity"), REPO)
        check.assert_called_once_with(cli, REPO, "main")
        create = next(call for call in cli.calls if call[0].endswith("/generate"))
        self.assertTrue(create[2]["private"])
        self.assertFalse(create[2]["include_all_branches"])
        self.assertEqual(cli.variables["COMMIT_EMAIL"], "12345+octocat@users.noreply.github.com")
        self.assertEqual(cli.variables["AUTO_COMMIT_ENABLED"], "true")

    def test_public_visibility_is_explicit(self):
        cli = FakeCLI()
        with patch.object(installer, "verify_installation", return_value="check"):
            installer.install(cli, REPO, public=True)
        create = next(call for call in cli.calls if call[0].endswith("/generate"))
        self.assertFalse(create[2]["private"])

    def test_dry_run_performs_only_reads(self):
        cli = FakeCLI()
        installer.install(cli, REPO, dry_run=True)
        self.assertTrue(all(call[1] == "GET" for call in cli.calls))
        self.assertEqual(cli.variables, {})

    def test_failed_check_leaves_new_installation_disabled(self):
        cli = FakeCLI()
        with patch.object(installer, "verify_installation", side_effect=installer.CLIError("check failed")):
            with self.assertRaises(installer.CLIError):
                installer.install(cli, REPO)
        self.assertEqual(cli.variables["AUTO_COMMIT_ENABLED"], "false")

    def test_existing_repository_is_never_overwritten(self):
        cli = FakeCLI({"private": True})
        with self.assertRaisesRegex(ValueError, "already exists"):
            installer.install(cli, REPO)
        self.assertTrue(all(call[1] == "GET" for call in cli.calls))

    def test_resume_checks_template_origin_without_recreating(self):
        metadata = {"private": True, "default_branch": "trunk", "fork": False,
                    "template_repository": {"full_name": installer.TEMPLATE}}
        cli = FakeCLI(metadata)
        with patch.object(installer, "verify_installation", return_value="check") as check:
            installer.install(cli, REPO, resume=True)
        check.assert_called_once_with(cli, REPO, "trunk")
        self.assertFalse(any(call[0].endswith("/generate") for call in cli.calls))

    def test_resume_rejects_forks_and_unrelated_repositories(self):
        for metadata in ({"private": True}, {"fork": True, "template_repository": {"full_name": installer.TEMPLATE}}):
            cli = FakeCLI(metadata)
            with self.assertRaisesRegex(ValueError, "independent"):
                installer.install(cli, REPO, resume=True)
            self.assertEqual(cli.variables, {})

    def test_missing_resume_target_is_not_created(self):
        cli = FakeCLI()
        with self.assertRaisesRegex(ValueError, "does not exist"):
            installer.install(cli, REPO, resume=True)
        self.assertEqual(cli.variables, {})

    def test_invalid_destinations_fail_before_repository_access(self):
        for value in ("-", "../repo", "other/repo", "a/b/c", "Eyfon/Auto-Commit", "..", "."):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    installer.repository_name(value, "octocat")

    def test_network_failure_is_not_treated_as_missing_repository(self):
        cli = Mock()
        cli.api.side_effect = [{"login": "octocat", "id": 12345}, installer.CLIError("HTTP 403")]
        with self.assertRaises(installer.CLIError):
            installer.install(cli, REPO)
        cli.variable.assert_not_called()


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def cli(self, conclusion="success", job="success"):
        cli = Mock()
        old = {"id": 1, "head_branch": "main"}
        new = {"id": 2, "head_branch": "main"}
        cli.api.side_effect = [
            {"workflow_runs": [old]}, None,
            {"workflow_runs": [new, old]},
            {"status": "completed", "conclusion": conclusion, "html_url": "check-url"},
            {"jobs": [{"name": "commit", "conclusion": job}]},
        ]
        return cli

    def test_checks_new_dispatch_and_successful_job(self):
        cli = self.cli()
        self.assertEqual(installer.verify_installation(cli, REPO, "main"), "check-url")
        self.assertIn("/actions/runs/2", cli.api.call_args_list[3].args[0])
        dispatch = cli.api.call_args_list[1]
        self.assertEqual(dispatch.args[2]["inputs"], {"verify_only": "true"})

    def test_failed_run_is_not_accepted(self):
        with self.assertRaisesRegex(installer.CLIError, "Verification failed"):
            installer.verify_installation(self.cli(conclusion="failure"), REPO, "main")

    def test_skipped_job_is_not_accepted_as_verification(self):
        with self.assertRaisesRegex(installer.CLIError, "did not run"):
            installer.verify_installation(self.cli(job="skipped"), REPO, "main")

    def test_timeout_does_not_claim_success(self):
        cli = Mock()
        cli.api.side_effect = [{"workflow_runs": []}, None]
        with patch.object(installer.time, "monotonic", side_effect=[0, 301]):
            with self.assertRaisesRegex(installer.CLIError, "timed out"):
                installer.verify_installation(cli, REPO, "main")


class TransportTests(unittest.TestCase):
    def test_payload_uses_stdin_and_arguments_do_not_use_a_shell(self):
        with patch.object(installer.shutil, "which", return_value="/path/gh"):
            cli = installer.GitHubCLI()
        result = subprocess.CompletedProcess([], 0, '{"ok":true}', "")
        with patch.object(installer.subprocess, "run", return_value=result) as run:
            self.assertEqual(cli.api("repos/a/b/generate", "POST", {"name": "repo"}), {"ok": True})
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), {"name": "repo"})
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(run.call_args.args[0][-2:], ["--input", "-"])

    def test_workflow_registration_retries_only_404(self):
        cli = Mock()
        cli.api.side_effect = [installer.CLIError("HTTP 404"), {"id": 10}]
        with patch.object(installer.time, "sleep"):
            self.assertEqual(installer.wait_for_workflow(cli, REPO), {"id": 10})
        cli.api.side_effect = installer.CLIError("HTTP 403")
        with self.assertRaises(installer.CLIError):
            installer.wait_for_workflow(cli, REPO)


if __name__ == "__main__":
    unittest.main()
