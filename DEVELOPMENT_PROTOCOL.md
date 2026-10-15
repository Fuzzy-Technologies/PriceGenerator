# F-Tech Services — GitHub Planning, Development & Review Protocol

> Canonical cross-project requirements for Fuzzy Technologies / F-Tech Services repositories.
>
> This document defines the default GitHub planning model, issue metadata, branch/PR workflow, review handoff, CI expectations, automatic Task completion, branch cleanup, and ChatGPT/GitHub connector behavior.

---

## 1. Core principle

Use **native GitHub capabilities as the source of truth** wherever GitHub provides a dedicated concept.

Do not encode project structure, work type, priority, effort, or milestone identity into issue titles.

Canonical planning model:

```text
Milestone
└── Umbrella Feature        # optional, only when useful for a large milestone
    └── Feature
        ├── Task
        ├── Task
        └── Task
```

A simpler project may use:

```text
Milestone
└── Feature
    ├── Task
    ├── Task
    └── Task
```

Use the extra Umbrella Feature level only when it materially improves navigation and decomposition.

Titles describe **work**. GitHub metadata describes **type, hierarchy, priority, effort, ownership, and planning context**.

---

## 2. Clean titles only

Issue titles must contain only human-readable work names.

Good:

```text
Establish reproducible legacy baseline
Modernize public API architecture
Add deterministic CI gate
Replace brute-force parabolic negation scan
```

Do not use planning prefixes such as:

```text
[TASK]
[FEATURE]
[ADR]
[TASK M1.2.3]
[FEATURE M1.2]
M0
M1
M1.2
```

Do not repeat native metadata in the title.

Legacy repositories may keep old prefixes when renaming would create noise, but all newly created work items should use clean titles.

---

## 3. Native planning model

Every planned implementation issue must have the applicable metadata set immediately:

```text
Type
Priority
Effort
Milestone
Assignee
Labels
Parent/sub-issue relationship
```

The native GitHub hierarchy is the source of truth.

Text such as:

```text
Parent feature: #123
Tracking milestone: #3
```

may remain for readability, but it does not replace the native relationship.

---

## 4. Feature

A Feature must have:

```text
Native Type = Feature
Priority    = required
Effort      = required
Milestone   = required
Assignee    = required
```

Recommended label when the repository uses type labels:

```text
feature
```

The label is supplementary. Native `Type = Feature` is authoritative.

A Feature should normally contain:

- Outcome / Goal
- Scope
- Acceptance criteria
- native sub-issues
- relevant ADR references
- dependencies when applicable

---

## 5. Umbrella Feature

An Umbrella Feature is optional and represents the overall result of a large Milestone.

Typical structure:

```text
Milestone
└── Umbrella Feature
    ├── Feature
    ├── Feature
    └── Feature
```

An Umbrella Feature must itself have normal Feature metadata:

```text
Type      = Feature
Priority  = required
Effort    = required
Milestone = required
Assignee  = required
```

Child Features must be attached as **native sub-issues**.

Do not create an Umbrella Feature only to imitate a Milestone. Use it when the extra navigation level is genuinely useful.

---

## 6. Task

A Task must have:

```text
Native Type = Task
Priority    = required
Effort      = required
Milestone   = required
Assignee    = required
Parent      = native Feature when applicable
```

Recommended label when used by the repository:

```text
task
```

A Task should normally contain:

- Deliverable
- Acceptance criteria
- parent Feature
- relevant ADR/dependency references
- test/evidence expectations

---

## 7. ADR issues

ADR decision work is planned work and must not remain metadata-free.

Default ADR issue metadata:

```text
Native Type = Task
Priority    = required
Effort      = required
Milestone   = required
Assignee    = required
```

Recommended labels:

```text
task
adr
```

If an ADR is specific to one Feature, attach it as a native sub-issue of that Feature.

Cross-cutting ADRs may remain directly under the Milestone without an artificial Feature parent.

The ADR document itself may retain a stable ADR number in its filename or document metadata. The planning issue title should remain human-readable unless the repository explicitly requires ADR numbers in issue titles.

---

## 8. Milestones

Milestones must be **native GitHub Milestones**.

Create them through the GitHub connector when supported, otherwise through the official API:

```text
POST /repos/{owner}/{repo}/milestones
```

A Milestone description should normally contain:

```text
Goal
Scope
Compatibility / design principles when relevant
Exit Criteria
```

Do not invent deadlines. Leave `due_on` empty if the roadmap uses soft or unspecified dates.

Milestone titles should be human-readable. Numeric prefixes such as `M0`, `M1` are optional project-specific conventions, not a cross-project requirement.

---

## 9. Assigning an issue to a Milestone

Use the native milestone number:

```text
PATCH /repos/{owner}/{repo}/issues/{issue_number}
```

Payload:

```json
{
  "milestone": 3
}
```

Apply native Milestones to:

- Umbrella Features
- Features
- Tasks
- ADR issues
- implementation PRs

---

## 10. Native Issue Type

Native Type is separate from labels.

Use:

```text
Feature -> Type = Feature
Task    -> Type = Task
ADR     -> Type = Task
```

If the current connector does not expose native Issue Type mutation, use the authenticated official GitHub API.

Example:

```powershell
$body = @{
    type = "Task"
} | ConvertTo-Json

$body | gh api `
    --method PATCH `
    repos/Fuzzy-Technologies/REPOSITORY/issues/123 `
    -H "Accept: application/vnd.github+json" `
    -H "X-GitHub-Api-Version: 2026-03-10" `
    --input -
```

Always read the issue back after mutation.

---

## 11. Priority and Effort

Fuzzy Technologies uses organization-level **Issue Fields**, not GitHub Projects fields.

Current known organization fields:

```text
Priority
Field ID: 22639629

Effort
Field ID: 22639632
```

Allowed Priority values:

```text
Urgent
High
Medium
Low
```

Allowed Effort values:

```text
High
Medium
Low
```

Before bulk work, verify current IDs:

```powershell
gh api `
  orgs/Fuzzy-Technologies/issue-fields `
  -H "X-GitHub-Api-Version: 2026-03-10" `
  --jq '.[] | {id, name, data_type, options}'
```

Do not assume a GitHub Project is required.

---

## 12. Setting Priority and Effort

Use:

```text
POST /repos/{owner}/{repo}/issues/{issue_number}/issue-field-values
```

Example:

```powershell
$body = @{
    issue_field_values = @(
        @{
            field_id = 22639629
            value    = "High"
        },
        @{
            field_id = 22639632
            value    = "Medium"
        }
    )
} | ConvertTo-Json -Depth 5

$body | gh api `
    --method POST `
    repos/Fuzzy-Technologies/REPOSITORY/issues/123/issue-field-values `
    -H "Accept: application/vnd.github+json" `
    -H "X-GitHub-Api-Version: 2026-03-10" `
    --input -
```

Read back the values after mutation.

---

## 13. Priority semantics

Use `Urgent` when the work blocks:

- correctness;
- security;
- compatibility;
- release;
- the next mandatory implementation stage.

Use `High` for important required work in the milestone.

Use `Medium` for normal planned work that does not block the nearest required stage.

Use `Low` for:

- optional improvements;
- exploratory work;
- performance experiments;
- future-facing work.

---

## 14. Effort semantics

Use `High` for:

- substantial implementation;
- major research;
- broad integration;
- high uncertainty.

Use `Medium` for a normal engineering task with several meaningful steps.

Use `Low` for small, bounded, well-understood work.

---

## 15. Native sub-issue hierarchy

Use native GitHub sub-issues instead of text-only relationships.

Canonical relationships:

```text
Umbrella Feature
└── Feature
    └── Task
```

or:

```text
Feature
└── Task
```

Do not build arbitrary deep Task -> Task -> Task trees without a clear architecture reason.

An implementation Task should normally have exactly one owning parent Feature.

---

## 16. Creating native parent/sub-issue relationships

Use:

```text
POST /repos/{owner}/{repo}/issues/{parent_issue_number}/sub_issues
```

Obtain the child database ID:

```powershell
$childId = gh api `
  repos/Fuzzy-Technologies/REPOSITORY/issues/124 `
  -H "X-GitHub-Api-Version: 2026-03-10" `
  --jq '.id'
```

Attach it:

```powershell
$body = @{
    sub_issue_id   = [long]$childId
    replace_parent = $true
} | ConvertTo-Json

$body | gh api `
    --method POST `
    repos/Fuzzy-Technologies/REPOSITORY/issues/123/sub_issues `
    -H "Accept: application/vnd.github+json" `
    -H "X-GitHub-Api-Version: 2026-03-10" `
    --input -
```

Verify the native parent afterward.

---

## 17. Labels

Labels are supplementary metadata.

Typical convention:

```text
Feature:
  Type  = Feature
  label = feature

Task:
  Type  = Task
  label = task

ADR:
  Type  = Task
  label = task
  label = adr
```

Use additional labels only when they improve filtering or automation, for example:

```text
ci
docs
security
compatibility
packaging
performance
```

Avoid creating label taxonomies that merely duplicate Milestone, Priority, Effort, or native Type.

---

# Development Workflow

## 18. Branch policy

Default development flow:

```text
master
  ↑
develop
  ↑
feature/task branch
```

Rules:

- implementation work starts from `develop`;
- no direct feature work on `master`;
- no direct feature work on `develop`;
- one isolated branch per coherent implementation stream;
- branch names should be short and descriptive.

Examples:

```text
feature/43-deterministic-ci-gate
feature/123-close-linked-tasks
fix/parabolic-negation-domain
docs/compatibility-contract
```

A branch may implement one Feature with several tightly coupled child Tasks when that is the natural atomic review unit.

Independent work should use independent branches and PRs.

---

## 19. Parallel development

Parallel work is allowed and encouraged when streams are genuinely independent.

Before starting parallel branches, verify:

- no direct dependency between the tasks;
- no expected conflict in the same core files;
- no shared migration that must land first;
- no incompatible API assumptions;
- each PR can be reviewed and merged independently.

Prefer parallel work from different Features or Milestones when that reduces file overlap.

Do not create fake parallelism that produces avoidable merge conflicts.

---

## 20. Pull Request as a managed work item

A PR has no native GitHub Issue Type. Do **not** try to assign one.

Every implementation PR must have:

```text
Assignee
Label(s)
Milestone
Base branch = develop
Linked Task(s) / Feature(s)
CI evidence
```

Default F-Tech assignee unless the project specifies otherwise:

```text
Tim55667757
```

PR labels should reflect the primary work class or area, for example:

```text
task
feature
ci
docs
security
packaging
```

At minimum, use the appropriate existing project label such as `task` for a Task implementation PR.

A PR must use the same native Milestone as its primary implementation issue.

---

## 21. PR title

Use a clean human-readable title.

Good:

```text
Add deterministic GitHub Actions quick gate
Close linked Tasks after merged pull requests
Correct parabolic fuzzy negation
```

Do not prefix PR titles with:

```text
[TASK]
[FEATURE]
M1
M1.2
```

GitHub metadata and linked issues already provide that context.

---

## 22. PR body

The PR body must include:

- explicit closing reference to the implemented Task;
- summary of changes;
- validation evidence;
- scope boundaries when useful;
- compatibility/security notes when relevant.

Canonical Task link:

```text
Closes #123
```

Accepted explicit completion keywords for F-Tech automation:

```text
Closes #123
Fixes #123
Resolves #123
Implements #123
```

Plain references such as:

```text
Related: #123
See #123
```

must **not** close the Task.

Do not use a closing keyword for a Feature unless the project intentionally wants that Feature to close automatically. The standard post-merge automation described below closes only native `Task` issues.

---

## 23. PR review ownership

PR merge remains human-controlled unless the user explicitly requests otherwise.

ChatGPT/AIna may:

- create branches;
- implement code;
- implement tests;
- create/update workflows;
- open PRs;
- assign PRs;
- label PRs;
- attach Milestones;
- inspect CI;
- respond to review comments;
- update the implementation.

Do not request formal review from the PR author when GitHub prohibits it.

For PRs created under `Tim55667757`, use:

```text
Assignee = Tim55667757
```

as the review/attention handoff.

---

## 24. Ready-for-review handoff

When implementation is ready for human review:

1. ensure PR metadata is complete;
2. ensure CI has run;
3. fix known CI failures before calling the PR ready;
4. add a comment to the implemented Task;
5. add a short status comment to the parent Feature when useful;
6. provide the direct PR URL.

Task comment should state:

- what was implemented;
- what tests/checks passed;
- which PR contains the change;
- that review is expected.

Example:

```text
Implementation is ready for review in PR #124:
https://github.com/Fuzzy-Technologies/REPOSITORY/pull/124

Implemented:
- ...
- ...

Validation: PASS — ...
Awaiting review and merge into develop.
```

Feature comment should briefly state which child Task is ready and link to the PR.

---

## 25. Direct links in chat

When referring to a GitHub object in discussion with the user, include a direct clickable link whenever practical.

Prefer:

```text
Task #43 — https://github.com/Fuzzy-Technologies/REPOSITORY/issues/43
PR #122 — https://github.com/Fuzzy-Technologies/REPOSITORY/pull/122
Feature #16 — https://github.com/Fuzzy-Technologies/REPOSITORY/issues/16
```

Do not make the user manually navigate from bare issue numbers when a direct link is available.

---

# CI / Automation Requirements

## 26. Deterministic PR gate

Each active engineering repository should have a fast deterministic PR gate appropriate to the technology stack.

For a Python project this normally includes:

- checkout;
- supported Python runtime;
- dependency installation;
- unit tests;
- import smoke;
- lint/type checks when already part of the project contract.

Do not claim CI PASS when the workflow only performs placeholder commands.

A historical workflow such as:

```text
ls -la
```

is not meaningful test evidence.

CI logs must expose the exact commands and environment sufficiently for reproduction.

---

## 27. Automatic closing of linked Tasks after merge

Every repository that uses the F-Tech PR workflow should have post-merge automation that closes explicitly linked **Task** issues after the PR is actually merged.

If this automation is missing, create it as a dedicated Task and PR before relying on automatic lifecycle management.

Recommended workflow path:

```text
.github/workflows/close-linked-tasks.yml
```

Recommended supporting parser:

```text
tools/pr_merge_links.py
```

Recommended tests:

```text
tests/test_pr_merge_links.py
```

The automation must:

- trigger on pull request lifecycle events;
- perform issue completion only when `pull_request.merged == true`;
- work for merge, squash, and rebase merge methods;
- parse explicit `Closes`, `Fixes`, `Resolves`, and `Implements` references;
- support multiple linked Tasks;
- deduplicate repeated references;
- ignore plain references;
- verify the referenced object is an Issue, not another PR;
- verify native GitHub `Type == Task`;
- never auto-close a Feature merely because it was mentioned;
- add a completion comment before closing the Task;
- close the Task with `state_reason = completed`;
- safely tolerate an already closed Task;
- attempt branch cleanup only after issue processing.

---

## 28. Reference implementation for linked-Task parser

A small deterministic parser is preferred over fragile shell-only parsing.

Example behavior:

```text
Closes #12
Fixes #13
Resolves #14
Implements #15
```

returns:

```text
12
13
14
15
```

This must be covered by unit tests for:

- supported keywords;
- case-insensitivity;
- accepted inflections;
- several issue references after one keyword;
- duplicate references;
- plain references that must not close anything;
- invalid/non-numeric references.

Do not deploy this automation without parser tests.

---

## 29. Reference post-merge Action behavior

A repository implementation should be equivalent to:

```yaml
name: Close linked Tasks after merge

on:
  pull_request:
    types:
      - opened
      - synchronize
      - reopened
      - closed
    branches:
      - develop
      - master

permissions:
  contents: write
  issues: write
  pull-requests: read

jobs:
  parser-tests:
    if: github.event.action != 'closed'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - run: python -m pip install pytest
      - run: python -m pytest -q tests/test_pr_merge_links.py

  close-linked-tasks:
    if: github.event.action == 'closed' && github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    env:
      GH_TOKEN: ${{ github.token }}
      GH_REPO: ${{ github.repository }}
      PR_NUMBER: ${{ github.event.pull_request.number }}
      PR_URL: ${{ github.event.pull_request.html_url }}
      PR_BODY: ${{ github.event.pull_request.body }}
      HEAD_REF: ${{ github.event.pull_request.head.ref }}
      HEAD_REPO: ${{ github.event.pull_request.head.repo.full_name }}
      BASE_REF: ${{ github.event.pull_request.base.ref }}

    steps:
      - uses: actions/checkout@v5
        with:
          ref: ${{ github.event.pull_request.base.ref }}

      - name: Close explicitly linked Tasks
        shell: bash
        run: |
          set -euo pipefail

          mapfile -t linked_issues < <(python tools/pr_merge_links.py)

          for issue_number in "${linked_issues[@]}"; do
            issue="$(gh api "repos/$GH_REPO/issues/$issue_number")"

            if [ "$(printf '%s' "$issue" | jq -r 'has("pull_request")')" = "true" ]; then
              continue
            fi

            issue_type="$(printf '%s' "$issue" | jq -r '.type.name // ""')"
            issue_state="$(printf '%s' "$issue" | jq -r '.state')"

            if [ "$issue_type" != "Task" ]; then
              continue
            fi

            if [ "$issue_state" = "closed" ]; then
              continue
            fi

            comment="$(jq -nc               --arg body "Implemented by merged PR #$PR_NUMBER ($PR_URL). Automatically marked completed after successful merge into $BASE_REF."               '{body:$body}')"

            printf '%s' "$comment" | gh api               --method POST               "repos/$GH_REPO/issues/$issue_number/comments"               --input - >/dev/null

            printf '%s' '{"state":"closed","state_reason":"completed"}' | gh api               --method PATCH               "repos/$GH_REPO/issues/$issue_number"               --input - >/dev/null
          done
```

The exact implementation may differ by language/tooling, but the invariants above are mandatory.

---

## 30. Branch deletion after merge

After a successful merge, the merged head branch should normally be deleted.

The automation may delete the branch only when:

- the PR branch belongs to the same repository;
- it is not `master`;
- it is not `develop`;
- it is not the current base branch.

Fork branches must not be deleted by the base repository workflow.

Branch deletion is cleanup, not correctness. Failure to delete the branch must not prevent Task completion.

If the user already deleted the branch manually, the workflow should tolerate that condition.

---

## 31. Issue lifecycle after implementation

When a Task implementation PR is opened and ready:

```text
Task remains OPEN
Task gets implementation comment
PR waits for review
```

After successful merge:

```text
post-merge Action
  -> adds completion comment
  -> closes linked Task as completed
  -> attempts branch cleanup
```

Features should **not** be automatically closed merely because one child Task merged.

A Feature is complete only when:

- required child Tasks are completed;
- acceptance criteria are satisfied;
- required evidence exists;
- no blocking review issue remains.

When a Feature becomes complete, add a final completion comment and close it deliberately.

The same rule applies to Umbrella Features.

---

## 32. Implementation comments

Every completed implementation stream must leave traceable comments in GitHub.

Before review:

```text
Task:
  implementation ready
  PR URL
  summary
  validation state
  awaiting review

Parent Feature:
  child Task implemented
  PR URL
  concise status
```

After merge, the automatic or manual completion comment should include:

- merged PR number;
- direct PR URL;
- target branch;
- validation result when useful.

The issue timeline must be sufficient to reconstruct what happened without reading chat history.

---

## 33. PR metadata checklist

Before reporting a PR as ready for review:

```text
[ ] base = develop
[ ] assignee set
[ ] suitable label(s) set
[ ] native milestone set
[ ] explicit Task-closing reference present
[ ] direct linked issue references present
[ ] PR body describes changes
[ ] validation evidence present
[ ] CI green, or failures explicitly reported
[ ] linked Task has implementation comment
[ ] parent Feature has status comment when appropriate
```

PRs do not have native Issue Type. Do not invent one.

---

## 34. Review and merge policy

Human review remains the default gate.

ChatGPT/AIna should not merge a PR unless the user explicitly asks to merge it.

When review comments arrive:

1. read all review threads;
2. classify each comment;
3. fix valid issues in the existing PR branch;
4. add/update tests when appropriate;
5. rerun CI;
6. respond to review threads;
7. report only verified PASS.

Do not open a replacement PR for ordinary review fixes.

---

## 35. Local validation by the user

GitHub Actions is the primary shared evidence surface, but local validation remains useful when:

- environment-specific behavior matters;
- old Python/runtime versions are needed;
- hardware benchmarks matter;
- packaging/install behavior needs local confirmation;
- external tools are unavailable on hosted runners.

When local confirmation is required, provide the exact commands to run.

Do not offload routine checks to the user when GitHub Actions can run them deterministically.

---

## 36. Evidence-first rule

Never report:

```text
created
linked
assigned
implemented
verified
PASS
closed
merged
```

unless the corresponding GitHub state was actually read back or the CI evidence was inspected.

A successful API call is not enough for critical metadata changes. Read the resulting object back.

A printed `PASS` line in a local script is not evidence if earlier commands failed.

---

# ChatGPT / Connector Rules

## 37. Tool selection

In any F-Tech Services chat:

1. inspect available GitHub connector actions;
2. use native connector actions whenever possible;
3. use the authenticated official GitHub API for unsupported native metadata;
4. do not ask the user to perform repetitive manual work when automation is available;
5. do not claim a capability is unavailable before checking the current tool surface.

The connector may lag behind newly added GitHub native fields. That is not the same as lacking GitHub permissions.

---

## 38. Write safety

Never modify `master` or `develop` directly for normal implementation work.

Use a branch and PR.

Temporary automation branches may be used only when:

- the connector lacks a required API mutation;
- the operation is isolated;
- default branches are untouched;
- the temporary branch/workflow is removed afterward.

Do not leave temporary workflows active after administrative work.

---

## 39. Bulk metadata operations

For bulk mutation:

1. perform one canary;
2. read it back;
3. continue only after verification;
4. use sequential or low-concurrency writes;
5. use short delays if rate limits are possible;
6. stop on unexplained validation errors;
7. perform an independent final verification pass.

Recommended delay for large GitHub metadata batches:

```text
0.5-1.0 second
```

---

## 40. Cleanup after temporary automation

After administrative or migration automation:

```text
[ ] temporary branch removed
[ ] temporary workflow unavailable on master/develop
[ ] no temporary source files remain
[ ] no active temporary workflow run remains where practical
[ ] final GitHub state independently verified
```

Historical completed Action runs may remain in GitHub history if deleting them would require pointless recursive cleanup automation.

---

# Project Bootstrap

## 41. Required GitHub automation for a new repository

During project bootstrap, inspect whether the repository already has:

- deterministic PR CI;
- linked-Task post-merge completion;
- safe merged-branch cleanup.

If the linked-Task automation is absent:

1. create a normal Task for it;
2. assign Type / Priority / Effort / Milestone / parent Feature;
3. implement it in a feature branch;
4. add parser/unit tests;
5. open a normal PR to `develop`;
6. set PR assignee / labels / Milestone;
7. review and merge it before relying on automated Task lifecycle.

Do not silently inject unreviewed workflow automation directly into `develop` or `master`.

---

## 42. Recommended order for a new project

1. inspect repository/default branches;
2. ensure `develop` exists;
3. define native Milestones;
4. create Umbrella Features only if useful;
5. create Features;
6. create Tasks;
7. create ADR Tasks;
8. assign all native metadata;
9. create native hierarchy;
10. verify planning state;
11. establish deterministic CI;
12. establish post-merge linked-Task automation;
13. start implementation branches;
14. open PRs to `develop`;
15. review;
16. merge;
17. auto-close Tasks and clean merged branches;
18. close Features only after their acceptance criteria are complete.

---

## 43. Language rule

For engineering repositories:

```text
Issue title            = English
Issue description      = English
Milestone title        = English
Milestone description  = English
ADR                     = English
PR title/body           = English
Code/docs               = English
Workflow names/steps    = English
```

Discussion with the user may remain Russian.

---

# Verification

## 44. Feature checklist

```text
[ ] clean title
[ ] native Type = Feature
[ ] Priority set
[ ] Effort set
[ ] correct native Milestone
[ ] correct assignee
[ ] useful label(s)
[ ] expected native sub-issues attached
[ ] acceptance criteria present
```

---

## 45. Task checklist

```text
[ ] clean title
[ ] native Type = Task
[ ] Priority set
[ ] Effort set
[ ] correct native Milestone
[ ] correct assignee
[ ] useful label(s)
[ ] correct native parent Feature
[ ] Deliverable present
[ ] Acceptance criteria present
```

---

## 46. ADR checklist

```text
[ ] clean title
[ ] native Type = Task
[ ] Priority set
[ ] Effort set
[ ] correct native Milestone
[ ] correct assignee
[ ] task/adr labels when used
[ ] native parent Feature when applicable
[ ] Context / Decision / Output documented
```

---

## 47. Milestone checklist

```text
[ ] native GitHub Milestone exists
[ ] human-readable title
[ ] complete English description
[ ] Goal documented
[ ] Scope documented
[ ] Exit Criteria documented
[ ] correct issues attached
[ ] no invented due date
```

---

## 48. PR checklist

```text
[ ] implementation branch from develop
[ ] clean PR title
[ ] base = develop
[ ] assignee set
[ ] suitable label(s) set
[ ] native Milestone set
[ ] explicit closing Task reference
[ ] direct issue references
[ ] change summary
[ ] validation evidence
[ ] CI green or failure honestly reported
[ ] Task implementation comment added
[ ] Feature status comment added when useful
[ ] ready for human review
```

---

## 49. Post-merge checklist

```text
[ ] PR actually merged
[ ] linked Tasks completed
[ ] completion comment present
[ ] Task state_reason = completed
[ ] merged branch deleted or safely skipped
[ ] Feature progress updated
[ ] no accidental Feature auto-close
[ ] final CI/merge evidence available
```

---

## 50. Canonical F-Tech development invariant

Planning:

```text
Milestone
└── Umbrella Feature (optional)
    └── Feature
        └── Task
```

Implementation:

```text
Task
  ↓
feature branch from develop
  ↓
code + tests + evidence
  ↓
PR -> develop
  ↓
PR metadata + Task/Feature comments
  ↓
CI PASS
  ↓
human review
  ↓
merge
  ↓
automatic Task completion
  ↓
safe branch cleanup
```

Metadata:

```text
Feature:
  Title     = clean
  Type      = Feature
  Priority  = set
  Effort    = set
  Milestone = set
  Assignee  = set

Task:
  Title     = clean
  Type      = Task
  Priority  = set
  Effort    = set
  Milestone = set
  Assignee  = set
  Parent    = native Feature

PR:
  Title     = clean
  Type      = none
  Assignee  = set
  Labels    = set
  Milestone = set
  Base      = develop
  Closes/Fixes/Resolves/Implements = linked Task
```

The GitHub issue/PR timeline and CI history must be sufficient to understand implementation status without relying on private chat history.

**Title describes the work. Native metadata describes planning. Branch/PR/CI history describes implementation.**
