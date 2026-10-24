"""The CI workflow and Dependabot config must stay read-only, pinned and secret-free."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "check.yml").read_text()
DEPENDABOT = (ROOT / ".github" / "dependabot.yml").read_text()

# `uses: owner/name@<40 hex characters> # v<version>`: a tag can be moved to different code
# after the fact, a full commit SHA can't, and the comment says which release it is.
PINNED_USES = re.compile(
    r"uses:\s+[\w.-]+/[\w./-]+@[0-9a-f]{40}\s+#\s+v\d+\.\d+\.\d+\S*"
)


def uses_lines() -> list[str]:
    lines = [line.strip().removeprefix("- ") for line in WORKFLOW.splitlines()]
    return [line for line in lines if line.startswith("uses:")]


def test_the_workflow_runs_make_check() -> None:
    assert "run: make check" in WORKFLOW


def test_every_action_is_pinned_to_a_sha_with_a_version_comment() -> None:
    assert uses_lines()
    assert [line for line in uses_lines() if not PINNED_USES.fullmatch(line)] == []


def test_the_workflow_only_reads_the_repository() -> None:
    assert "permissions:\n  contents: read\n" in WORKFLOW
    assert "write" not in WORKFLOW.split("permissions:")[1].split("concurrency:")[0]


def test_checkout_does_not_persist_credentials() -> None:
    assert uses_lines() and WORKFLOW.count("persist-credentials: false") == len(
        [line for line in uses_lines() if "actions/checkout" in line]
    )


def test_the_workflow_runs_on_a_pinned_runner_with_pinned_tools() -> None:
    assert "runs-on: ubuntu-24.04" in WORKFLOW
    assert 'UV_VERSION: "' in WORKFLOW
    assert "secrets." not in WORKFLOW


def test_dependabot_updates_github_actions_weekly_and_nothing_else() -> None:
    assert DEPENDABOT.count("package-ecosystem:") == 1
    assert 'package-ecosystem: "github-actions"' in DEPENDABOT
    assert 'interval: "weekly"' in DEPENDABOT


def test_the_checks_run_on_python_3_10_and_3_14() -> None:
    assert 'python-version: ["3.10", "3.14"]' in WORKFLOW
    assert "PYTHON_VERSION: ${{ matrix.python-version }}" in WORKFLOW
