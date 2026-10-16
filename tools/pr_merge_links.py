"""Complete explicitly linked native Tasks after a trusted merged pull request."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


KEYWORD = r"(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?|implement(?:s|ed)?)"
REFERENCE = re.compile(
    r"(?:(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+))?"
    r"#(?P<number>[1-9][0-9]*)(?![\w#/-]|\.[0-9])"
    r"|https://github\.com/(?P<url_owner>[A-Za-z0-9_.-]+)/"
    r"(?P<url_repo>[A-Za-z0-9_.-]+)/issues/(?P<url_number>[1-9][0-9]*)"
    r"(?![\w#/?-]|\.[0-9])",
    re.IGNORECASE,
)
INSTRUCTION = re.compile(
    rf"^\s*(?:(?:[-*+]|[0-9]+[.)])\s+)?(?:\[[ xX]\]\s+)?"
    rf"{KEYWORD}\b\s*:?[ \t]*",
    re.IGNORECASE,
)
SEPARATOR = re.compile(rf"\s*(?:,\s*(?:and\s+)?|and\s+|&\s*|;\s*(?:{KEYWORD}\s*:?[ \t]*)?)", re.IGNORECASE)


def ParseTaskReferences(body: str, repository: str = "") -> list[int]:
    """Read explicit completion lines, ignoring quoted examples and other repos."""

    visible = re.sub(r"<!--.*?(?:-->|\Z)", "", body, flags=re.DOTALL)
    issue_numbers = []
    fence_character = ""
    fence_length = 0

    for line in visible.splitlines():
        stripped = line.lstrip()
        fence = re.match(r"(`{3,}|~{3,})", stripped)

        if fence_character:
            if fence and fence.group()[0] == fence_character and len(fence.group()) >= fence_length:
                fence_character = ""

            continue

        if line.startswith(("    ", "\t")) or stripped.startswith(">"):
            continue

        if fence:
            fence_character = fence.group()[0]
            fence_length = len(fence.group())
            continue

        line = re.sub(r"(`+).*?\1", " INLINE_CODE ", line)
        instruction = INSTRUCTION.match(line)

        if not instruction:
            continue

        remaining = line[instruction.end():]

        while reference := REFERENCE.match(remaining):
            owner = reference.group("owner") or reference.group("url_owner")
            repo = reference.group("repo") or reference.group("url_repo")
            number = int(reference.group("number") or reference.group("url_number"))

            if owner is None or f"{owner}/{repo}".lower() == repository.lower():
                if number not in issue_numbers:
                    issue_numbers.append(number)

            remaining = remaining[reference.end():]
            separator = SEPARATOR.match(remaining)

            if not separator:
                break

            remaining = remaining[separator.end():]

    return issue_numbers


class ApiError(RuntimeError):
    """Expose a safe status code without leaking response data or credentials."""

    def __init__(self, status: int, message: str) -> None:
        """Record the transport status for explicit missing-resource handling."""

        super().__init__(message)
        self.status = status


class GitHubApi:
    """Use only the official GitHub REST origin with a bounded timeout."""

    def __init__(self, token: str) -> None:
        """Keep the token private to outbound request headers."""

        if not token:
            raise ValueError("GH_TOKEN is required for completion.")

        self._token = token

    def Request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        """Send JSON and report failures without echoing token or response body."""

        if not path.startswith("repos/") or "?" in path or "#" in path:
            raise ValueError("Only repository REST paths are accepted.")

        request = Request(
            f"https://api.github.com/{path}",
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "PriceGenerator-task-lifecycle",
            },
        )

        try:
            with urlopen(request, timeout=30) as response:
                data = response.read()

            return json.loads(data) if data else None

        except HTTPError as error:
            raise ApiError(error.code, f"GitHub {method} failed with HTTP {error.code}.") from None

        except (URLError, TimeoutError, ValueError) as error:
            raise ApiError(0, f"GitHub {method} failed: {type(error).__name__}.") from None


def CleanMergedBranch(pull_request: dict[str, Any], repository: dict[str, Any], api: GitHubApi) -> str:
    """Delete only an unprotected same-repository branch still at the merged head."""

    head = pull_request.get("head") or {}
    head_repo = head.get("repo") or {}
    base = pull_request.get("base") or {}
    branch = head.get("ref")
    protected_names = {"master", "main", "develop", base.get("ref"), repository.get("default_branch")}

    if head_repo.get("full_name") != repository["full_name"]:
        return "skipped-fork"

    if not isinstance(branch, str) or branch in protected_names or not re.fullmatch(r"[0-9a-f]{40}", head.get("sha") or ""):
        return "skipped-protected-or-invalid"

    prefix = f"repos/{repository['full_name']}"
    encoded_branch = quote(branch, safe="")

    try:
        current = api.Request("GET", f"{prefix}/branches/{encoded_branch}")

        if current.get("protected") is not False or current.get("commit", {}).get("sha") != head["sha"]:
            return "skipped-protected-or-moved"

        api.Request("DELETE", f"{prefix}/git/refs/heads/{encoded_branch}")

        return "deleted"

    except ApiError as error:
        if error.status == 404:
            return "already-absent"

        print(f"Branch cleanup skipped: {error}", file=sys.stderr)

        return "cleanup-failed"


def CompleteLinkedTasks(event: dict[str, Any], api: GitHubApi) -> dict[str, Any]:
    """Verify a same-repository merge, complete Tasks, then attempt branch cleanup."""

    pull_request = event.get("pull_request") or {}

    if event.get("action") != "closed" or pull_request.get("merged") is not True:
        return {"completed": [], "cleanup": "skipped-unmerged"}

    repository = event.get("repository") or {}
    repository_name = repository.get("full_name", "")

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository_name):
        raise ValueError("A valid repository identity is required.")

    base = pull_request.get("base") or {}
    head = pull_request.get("head") or {}

    if (base.get("repo") or {}).get("full_name") != repository_name or base.get("ref") not in {"develop", "master"}:
        raise ValueError("Only merges into this repository's develop or master are allowed.")

    if (head.get("repo") or {}).get("full_name") != repository_name:
        return {"completed": [], "cleanup": "skipped-fork"}

    pr_number = pull_request.get("number")

    if type(pr_number) is not int or pr_number < 1:
        raise ValueError("A positive pull request number is required.")

    issue_numbers = ParseTaskReferences(pull_request.get("body") or "", repository_name)
    completed = []
    pr_url = f"https://github.com/{repository_name}/pull/{pr_number}"

    for issue_number in issue_numbers:
        path = f"repos/{repository_name}/issues/{issue_number}"

        try:
            issue = api.Request("GET", path)

        except ApiError as error:
            if error.status == 404:
                continue

            raise

        if "pull_request" in issue or (issue.get("type") or {}).get("name") != "Task" or issue.get("state") == "closed":
            continue

        if issue.get("state") != "open":
            raise ValueError(f"Unexpected state for Task #{issue_number}; stopping completion.")

        comment = (
            f"Implemented by merged PR #{pr_number} ({pr_url}). "
            f"Automatically marked completed after merge into {base['ref']}."
        )
        api.Request("POST", f"{path}/comments", {"body": comment})
        api.Request("PATCH", path, {"state": "closed", "state_reason": "completed"})
        verified = api.Request("GET", path)

        if verified.get("state") != "closed" or verified.get("state_reason") != "completed":
            raise ValueError(f"Task #{issue_number} completion could not be verified.")

        completed.append(issue_number)

    return {"completed": completed, "cleanup": CleanMergedBranch(pull_request, repository, api)}


def Main() -> None:
    """Parse PR_BODY locally or process the GitHub event when explicitly requested."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--complete", action="store_true", help="Complete Tasks using GITHUB_EVENT_PATH and GH_TOKEN.")
    arguments = parser.parse_args()

    if not arguments.complete:
        numbers = ParseTaskReferences(os.environ.get("PR_BODY", ""), os.environ.get("GITHUB_REPOSITORY", ""))

        for issue_number in numbers:
            print(issue_number)

        return

    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))

    if event.get("repository", {}).get("full_name") != os.environ.get("GITHUB_REPOSITORY"):
        raise ValueError("Event repository does not match the workflow repository.")

    print(json.dumps(CompleteLinkedTasks(event, GitHubApi(os.environ.get("GH_TOKEN", "")))))


if __name__ == "__main__":
    Main()
