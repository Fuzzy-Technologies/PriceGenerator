"""Exercise parsing, Task completion and failure-safe cleanup without GitHub I/O."""

import copy
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from tools import pr_merge_links


REPOSITORY = "Fuzzy-Technologies/PriceGenerator"
PREFIX = f"repos/{REPOSITORY}"
HEAD_SHA = "a" * 40


def MakeEvent() -> dict:
    """Create a same-repository merged event with explicit Task references."""

    return {
        "action": "closed",
        "repository": {"full_name": REPOSITORY, "default_branch": "master"},
        "pull_request": {
            "number": 100,
            "merged": True,
            "body": "Closes #12, #13",
            "base": {"ref": "develop", "repo": {"full_name": REPOSITORY}},
            "head": {"ref": "feature/78-ci", "sha": HEAD_SHA, "repo": {"full_name": REPOSITORY}},
        },
    }


class FakeApi:
    """Record ordered API operations and emulate isolated issue state."""

    def __init__(self) -> None:
        """Initialize native Tasks and an unprotected branch at the merged head."""

        self.issues = {
            12: {"type": {"name": "Task"}, "state": "open"},
            13: {"type": {"name": "Task"}, "state": "open"},
        }
        self.branch = {"protected": False, "commit": {"sha": HEAD_SHA}}
        self.calls = []
        self.failures = {}
        self.persist_close = True

    def Request(self, method: str, path: str, payload: dict | None = None):
        """Execute the minimal fake API while retaining operation order."""

        self.calls.append((method, path, payload))

        if (method, path) in self.failures:
            raise self.failures[method, path]

        if "/branches/" in path:
            return copy.deepcopy(self.branch)

        if method == "DELETE":
            return None

        number = int(path.split("/issues/")[1].split("/")[0])

        if number not in self.issues:
            raise pr_merge_links.ApiError(404, "Not found")

        if method == "PATCH" and self.persist_close:
            self.issues[number].update(payload)

        return copy.deepcopy(self.issues[number])


@pytest.mark.parametrize("keyword", ["close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved", "implement", "implements", "implemented", "ClOsEs"])
def test_AcceptExplicitCompletionKeywords(keyword: str) -> None:
    """Support the documented completion vocabulary case-insensitively."""

    assert pr_merge_links.ParseTaskReferences(f"{keyword} #12.") == [12], "Explicit completion reference must be recognized."


def test_MultipleReferencesAndDeduplication() -> None:
    """Preserve explicit order while accepting lists and repeated keywords."""

    body = "- [x] Closes: #12, #13 and #14; fixes #15\nImplements #13 & #16\n2. resolves #17"

    assert pr_merge_links.ParseTaskReferences(body) == [12, 13, 14, 15, 16, 17], "Completion lists must be ordered and deduplicated."


def test_OnlyExplicitSameRepositoryReferences() -> None:
    """Permit qualified own references and ignore other repository identities."""

    body = (
        "Closes Other/Repository#20, #12\n"
        "Closes Fuzzy-Technologies/PriceGenerator#13\n"
        "Resolves https://github.com/fuzzy-technologies/pricegenerator/issues/14\n"
        "Fixes https://github.com/Other/Repository/issues/15\n"
        "Closes #16, related to #17"
    )

    assert pr_merge_links.ParseTaskReferences(body, REPOSITORY) == [12, 13, 14, 16], "Other repos and unrelated trailing mentions must never close."


@pytest.mark.parametrize("body", [
    "Related: #12", "See #12", "Closes #oops", "Closes #0", "Closes #12oops", "Closes #12.3",
    "Closes #-12", "Closes #12/issue", "Closes #12#13", "Closes #0012", "Recloses #12",
    "`Closes #12`", "Closes `#12` #13", '> Closes #12', '"Closes #12"',
    "    Closes #12", "\tCloses #12", "[Closes #12](https://example.com)",
    "```text\nCloses #12\n```", "~~~~\nCloses #12\n~~~~", "<!-- Closes #12 -->",
    "<!--\nCloses #12\n-->", "<!--\nCloses #12", "Closes https://github.com/other/repo/pull/12",
    "Closes https://github.com/other/repo/issues/12abc",
])
def test_IgnoreExamplesAndInvalidOrPlainReferences(body: str) -> None:
    """Reject ambiguous prose, code, quotes and malformed identifiers."""

    assert pr_merge_links.ParseTaskReferences(body) == [], "Only an explicit valid completion instruction may close a Task."


def test_FenceLengthAndClosingMarker() -> None:
    """A shorter fence or the other fence character must not end a code block."""

    body = "````\n```\nCloses #1\n~~~\nCloses #2\n````\nCloses #3"

    assert pr_merge_links.ParseTaskReferences(body) == [3], "Examples inside a fenced block must remain ignored."


def test_CompleteNativeTasksBeforeDeletingBranch() -> None:
    """Comment, close and verify every Task before branch cleanup."""

    api = FakeApi()
    result = pr_merge_links.CompleteLinkedTasks(MakeEvent(), api)

    assert result == {"completed": [12, 13], "cleanup": "deleted"}, "Both native Tasks should complete."
    assert [call[0] for call in api.calls] == ["GET", "POST", "PATCH", "GET"] * 2 + ["GET", "DELETE"], "Comments and verification must precede cleanup."
    assert api.calls[2][2] == {"state": "closed", "state_reason": "completed"}, "Closure reason must be completed."
    assert f"https://github.com/{REPOSITORY}/pull/100" in api.calls[1][2]["body"], "Completion comment must identify the merged PR."
    assert api.calls[-1][1] == f"{PREFIX}/git/refs/heads/feature%2F78-ci", "Branch names must be URL-encoded."


@pytest.mark.parametrize("replacement", [
    {"type": {"name": "Feature"}, "state": "open"},
    {"type": {"name": "Bug"}, "state": "open"},
    {"type": {"name": "task"}, "state": "open"},
    {"labels": ["task"], "state": "open"},
    {"type": None, "state": "open"},
    {"type": {"name": "Task"}, "state": "closed", "state_reason": "not_planned"},
    {"type": {"name": "Task"}, "state": "open", "pull_request": {}},
])
def test_SkipNonTaskPullRequestAndClosedIssues(replacement: dict) -> None:
    """Native type is authoritative and closed issues remain untouched."""

    api = FakeApi()
    api.issues[12] = replacement
    result = pr_merge_links.CompleteLinkedTasks(MakeEvent(), api)

    assert result["completed"] == [13], "Only the open native Task should complete."
    assert not any(method in {"PATCH", "POST"} and "/issues/12" in path for method, path, _ in api.calls), "Skipped objects must not be mutated."


def test_MissingIssueIsHarmless() -> None:
    """An absent referenced issue must not prevent other Task completion."""

    api = FakeApi()
    del api.issues[12]

    assert pr_merge_links.CompleteLinkedTasks(MakeEvent(), api)["completed"] == [13], "Missing issues must be skipped safely."


@pytest.mark.parametrize("method,suffix", [("GET", ""), ("POST", "/comments"), ("PATCH", "")])
def test_FailedTaskOperationStopsCleanup(method: str, suffix: str) -> None:
    """A denied read, failed comment or failed close cannot delete the branch."""

    api = FakeApi()
    api.failures[method, f"{PREFIX}/issues/12{suffix}"] = pr_merge_links.ApiError(403, "Denied")

    with pytest.raises(pr_merge_links.ApiError, match="Denied"):
        pr_merge_links.CompleteLinkedTasks(MakeEvent(), api)

    assert not any(call[0] == "DELETE" for call in api.calls), "Failed Task processing must prevent cleanup."

    if method == "POST":
        assert not any(call[0] == "PATCH" for call in api.calls), "A completion comment is required before closure."


def test_UnverifiedClosurePreventsCleanup() -> None:
    """A successful HTTP response alone does not prove Task completion."""

    api = FakeApi()
    api.persist_close = False

    with pytest.raises(ValueError, match="could not be verified"):
        pr_merge_links.CompleteLinkedTasks(MakeEvent(), api)

    assert not any(call[0] == "DELETE" for call in api.calls), "Unverified completion must preserve the branch."


def test_UnknownIssueStateFailsClosed() -> None:
    """Unexpected API data must not be interpreted as an open Task."""

    api = FakeApi()
    api.issues[12]["state"] = "unknown"

    with pytest.raises(ValueError, match="Unexpected state"):
        pr_merge_links.CompleteLinkedTasks(MakeEvent(), api)

    assert len(api.calls) == 1, "Unexpected issue state must stop all mutations."


@pytest.mark.parametrize("merged", [False, None, "true", 1])
def test_UnmergedEventCannotMutate(merged) -> None:
    """Only the JSON boolean true authorizes completion."""

    event = MakeEvent()
    event["pull_request"]["merged"] = merged
    api = FakeApi()

    assert pr_merge_links.CompleteLinkedTasks(event, api)["cleanup"] == "skipped-unmerged", "Unmerged events must be ignored."
    assert api.calls == [], "Unmerged events must not call GitHub."


def test_NonClosedAndForkEventsCannotMutate() -> None:
    """Read-only PR lifecycle events and fork heads must be harmless."""

    api = FakeApi()
    event = MakeEvent()
    event["action"] = "synchronize"
    pr_merge_links.CompleteLinkedTasks(event, api)
    event = MakeEvent()
    event["pull_request"]["head"]["repo"] = {"full_name": "other/fork"}

    assert pr_merge_links.CompleteLinkedTasks(event, api)["cleanup"] == "skipped-fork", "Fork lifecycle uses the documented manual fallback."
    assert api.calls == [], "Fork and non-closed events must not call the write API."


@pytest.mark.parametrize("branch", ["master", "main", "develop", "release"])
def test_DefaultAndIntegrationBranchesCannotBeDeleted(branch: str) -> None:
    """Protect permanent branches, including a custom default branch."""

    event = MakeEvent()
    event["repository"]["default_branch"] = "release"
    event["pull_request"]["head"]["ref"] = branch
    api = FakeApi()
    result = pr_merge_links.CompleteLinkedTasks(event, api)

    assert result["completed"] == [12, 13], "Cleanup exclusions must not prevent completion."
    assert result["cleanup"] == "skipped-protected-or-invalid", "Permanent branches must survive cleanup."


@pytest.mark.parametrize("branch", [{"protected": True, "commit": {"sha": HEAD_SHA}}, {"protected": False, "commit": {"sha": "b" * 40}}, {"commit": {"sha": HEAD_SHA}}])
def test_ProtectedOrMovedBranchIsRetained(branch: dict) -> None:
    """Never delete a protected branch or commits added after the merge."""

    api = FakeApi()
    api.branch = branch

    assert pr_merge_links.CompleteLinkedTasks(MakeEvent(), api)["cleanup"] == "skipped-protected-or-moved", "A changed or protected branch must be preserved."
    assert not any(call[0] == "DELETE" for call in api.calls), "Unsafe branch deletion must never be attempted."


@pytest.mark.parametrize("method,status,expected", [("GET", 404, "already-absent"), ("DELETE", 404, "already-absent"), ("GET", 403, "cleanup-failed"), ("DELETE", 422, "cleanup-failed")])
def test_CleanupFailureDoesNotUndoTaskCompletion(method: str, status: int, expected: str) -> None:
    """Missing branches and API cleanup errors do not invalidate completed Tasks."""

    api = FakeApi()
    endpoint = "branches/feature%2F78-ci" if method == "GET" else "git/refs/heads/feature%2F78-ci"
    api.failures[method, f"{PREFIX}/{endpoint}"] = pr_merge_links.ApiError(status, "Cleanup unavailable")

    assert pr_merge_links.CompleteLinkedTasks(MakeEvent(), api) == {"completed": [12, 13], "cleanup": expected}, "Cleanup must be best effort after completion."


@pytest.mark.parametrize("mutation", ["repository", "base-repository", "base-branch", "pr-number"])
def test_RejectInvalidEventIdentity(mutation: str) -> None:
    """Validate event identity before constructing any mutation paths."""

    event = MakeEvent()

    if mutation == "repository":
        event["repository"]["full_name"] = "https://example.invalid/x"

    elif mutation == "base-repository":
        event["pull_request"]["base"]["repo"]["full_name"] = "other/repository"

    elif mutation == "base-branch":
        event["pull_request"]["base"]["ref"] = "unexpected"

    else:
        event["pull_request"]["number"] = True

    api = FakeApi()

    with pytest.raises(ValueError):
        pr_merge_links.CompleteLinkedTasks(event, api)

    assert api.calls == [], "Invalid event identity must cause no API calls."


def test_HttpRequestContractAndNoTokenInErrors(monkeypatch) -> None:
    """Pin origin, timeout, API version and credential-safe error handling."""

    def RaiseDenied(request, timeout):
        """Inspect the outbound request, then emulate a denied GitHub call."""

        assert request.full_url == f"https://api.github.com/{PREFIX}/issues/12", "API requests must use the official origin."
        assert request.headers["X-github-api-version"] == "2026-03-10", "Native issue type access requires the selected API version."
        assert timeout == 30, "Network operations must have a bounded timeout."

        raise HTTPError(request.full_url, 403, "sensitive response", None, None)

    monkeypatch.setattr(pr_merge_links, "urlopen", RaiseDenied)

    with pytest.raises(pr_merge_links.ApiError, match="HTTP 403") as captured:
        pr_merge_links.GitHubApi("private-token").Request("GET", f"{PREFIX}/issues/12")

    assert "private-token" not in str(captured.value), "Errors must not disclose credentials."
    assert "sensitive" not in str(captured.value), "Errors must not echo remote response data."


def test_NetworkFailureIsSafe(monkeypatch) -> None:
    """Connection errors must expose neither URLs nor credentials."""

    def RaiseOffline(*args, **kwargs):
        """Emulate an unavailable transport without contacting GitHub."""

        raise URLError("sensitive detail")

    monkeypatch.setattr(pr_merge_links, "urlopen", RaiseOffline)

    with pytest.raises(pr_merge_links.ApiError, match="URLError"):
        pr_merge_links.GitHubApi("private-token").Request("GET", f"{PREFIX}/issues/12")


def test_RejectMissingTokenAndForeignApiPath() -> None:
    """No unauthenticated completion or alternate origin is allowed."""

    with pytest.raises(ValueError, match="GH_TOKEN"):
        pr_merge_links.GitHubApi("")

    with pytest.raises(ValueError, match="repository REST paths"):
        pr_merge_links.GitHubApi("test").Request("GET", "https://example.invalid")


def test_CommandLineParserIsReadOnly(monkeypatch, capsys) -> None:
    """Default invocation only prints parsed numbers and needs no token."""

    monkeypatch.setattr("sys.argv", ["pr_merge_links.py"])
    monkeypatch.setenv("PR_BODY", "Closes #12, #13")
    pr_merge_links.Main()

    assert capsys.readouterr().out == "12\n13\n", "Local parser output must contain only explicit issue numbers."


def test_CommandLineCompletionChecksWorkflowIdentity(monkeypatch, tmp_path) -> None:
    """Cross-repository event files cannot authorize completion."""

    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(MakeEvent()), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["pr_merge_links.py", "--complete"])
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_REPOSITORY", "other/repository")

    with pytest.raises(ValueError, match="does not match"):
        pr_merge_links.Main()


@pytest.mark.parametrize("body,expected", [(b'{"state":"open"}', {"state": "open"}), (b"", None)])
def test_HttpJsonAndEmptyResponses(monkeypatch, body: bytes, expected) -> None:
    """Support normal JSON responses and the empty deletion response."""

    def OpenResponse(request, timeout):
        """Return an in-memory HTTP body without opening a connection."""

        assert json.loads(request.data) == {"state": "closed"}, "Mutation payload must be serialized as JSON."

        return io.BytesIO(body)

    monkeypatch.setattr(pr_merge_links, "urlopen", OpenResponse)

    assert pr_merge_links.GitHubApi("test").Request("PATCH", f"{PREFIX}/issues/12", {"state": "closed"}) == expected, "Transport must decode JSON and empty responses."


def test_CleanupDirectlyRejectsFork() -> None:
    """The cleanup helper independently enforces repository ownership."""

    event = MakeEvent()
    event["pull_request"]["head"]["repo"] = None
    api = FakeApi()

    assert pr_merge_links.CleanMergedBranch(event["pull_request"], event["repository"], api) == "skipped-fork", "Deleted or fork repositories must never be cleaned up."
    assert api.calls == [], "Fork cleanup must not call the API."


def test_CommandLineCompletionUsesValidatedEvent(monkeypatch, tmp_path, capsys) -> None:
    """The explicit completion entry point processes a validated event."""

    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(MakeEvent()), encoding="utf-8")
    api = FakeApi()
    monkeypatch.setattr("sys.argv", ["pr_merge_links.py", "--complete"])
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setattr(pr_merge_links, "GitHubApi", lambda token: api)
    pr_merge_links.Main()

    assert json.loads(capsys.readouterr().out)["completed"] == [12, 13], "CLI must report verified completed Tasks."
