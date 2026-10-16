# Release verification and PyPI publication

Release code lives in `.github/workflows/release.yml`. It runs **only by manual
dispatch on `master`**. A push, branch name, tag push, PR, or ordinary CI run
never uploads a package. The removed Travis workflow is no longer a release
path. `pricegenerator/_version.py` remains the sole version source. This release
candidate sets it to `2.0.0`; that source change does not itself publish files.
Future releases need separately reviewed version changes. Unreleased development
versions use a `.devN` suffix and can be verified but cannot publish.

## Configure the existing PyPI project

A project owner signs in to [pricegenerator publishing settings](https://pypi.org/manage/project/pricegenerator/settings/publishing/).
Add a **GitHub Actions** Trusted Publisher to this existing project with these
exact fields:

| PyPI field | Value |
| --- | --- |
| Owner | `Fuzzy-Technologies` |
| Repository name | `PriceGenerator` |
| Workflow filename | `release.yml` |
| Environment name | `pypi` |

The workflow field takes the filename alone, not `.github/workflows/release.yml`.
Use the existing project, rather than registering a pending publisher for a new
project. No API token, GitHub secret, username, or password is needed. PyPI
validates the workflow identity and issues short-lived credentials. The
publisher belongs to PyPI account configuration and cannot be installed by
committing this repository.

In [GitHub environment settings](https://github.com/Fuzzy-Technologies/PriceGenerator/settings/environments),
create `pypi`. Add one or more trusted human maintainers under **Required
reviewers**, save the rule, and disable administrator bypass. If independent
review is available, enable **Prevent self-review**; otherwise a sole maintainer
must be able to approve their own dispatch. Restrict deployment branches to the
selected branch `master`. Read back the saved reviewer and branch restrictions.
Only a repository administrator can configure this environment. The workflow
checks that required reviewers exist before a publishing run builds candidates;
a missing or unreadable rule fails with setup guidance. Verification-only runs
do not require PyPI configuration or this environment.

Keep old PyPI releases and project history. Disable the old Travis integration
so its historical configuration cannot run on old release branches. After the
new publisher has successfully published and its provenance has been verified,
revoke obsolete upload tokens in their account/service settings and remove an
old Trusted Publisher only if one exists and is no longer used. Deleting the
project or past releases is unnecessary.

## Review candidates before enabling publication

1. Merge the reviewed implementation through `develop` into `master`, including
   the final reviewed version literal and release notes. Require green Python
   quality jobs and the chart runtime gate for that commit.
2. Create a version tag `v<canonical-version>` at **exactly the current master
   HEAD**, after reviewing the commit. Publication requires the latest quality
   and chart runtime workflow runs for that exact SHA to be completed successfully;
   missing, pending, skipped, failed or wrong-commit evidence blocks publication.
   The workflows run on master pushes, so reuse their recorded green results.
   Tags that point merely to an ancestor of
   master fail the check. Development tags can verify candidates; development
   and local versions cannot publish.
3. Open [the release workflow](https://github.com/Fuzzy-Technologies/PriceGenerator/actions/workflows/release.yml),
   choose **Run workflow**, select `master`, enter the existing exact version
   tag, and leave **publish** unchecked.
4. Inspect the successful run's `release-distributions` artifact, `SHA256SUMS`,
   build/metadata logs, and all four Python verification jobs. Each job installs
   the wheel and the sdist into separate temporary environments outside the
   checkout. It exercises modern generation, canonical CSV, manifest replay,
   CLI, SVG, offline HTML, asset hashes/notices, and actual PNG/JPEG rendering.
   The core installation must contain neither obsolete backends nor optional
   raster/notebook dependencies. No checkout import can satisfy the smoke.
5. When publication is authorized, run the workflow on the same master/tag with
   **publish** checked. This run builds its own reviewed candidate **once**,
   uploads its wheel and sdist as one immutable Actions artifact, and verifies
   those exact downloaded bytes across CPython 3.10–3.13. Review **this run's**
   hashes and verification evidence before approving the pending `pypi` job.
   The earlier verification run's artifacts are not silently reused.
6. A configured required reviewer approves the pending environment deployment.
   The publish job downloads the same artifact, checks its recorded hashes,
   copies only the wheel and sdist into the upload directory, then uses PyPI
   Trusted Publishing with digital attestations. It has `id-token: write` only;
   build and verification jobs have no publication identity. It never rebuilds
   or uses `skip-existing` to conceal a duplicate upload.
7. Read back the published [project files](https://pypi.org/project/pricegenerator/#files),
   version, SHA-256 hashes and provenance. Install that exact public version in a
   fresh environment and repeat the modern smoke before declaring release done.
   Record the workflow URL and final artifact hashes in the release evidence.

A failed or partially completed upload needs inspection of PyPI's actual state
before another run. PyPI file identities cannot be overwritten. Resolve the
cause, and use a new reviewed version where necessary; do not remove historical
files to make a failed rerun appear successful.

## Local verification

From a locked development environment, without any PyPI credentials:

```bash
python -m pytest -q tests/test_packaging.py tests/test_release_contract.py
python -m build
python -m twine check --strict dist/*
python tools/release_verify.py --artifacts dist
python tools/release_install.py dist
```

`python -m build` builds the wheel from its freshly created sdist, exposing
source-distribution omissions. The tag check rejects tracked changes and
nonignored untracked files; distributions/caches are already ignored. Retired
runtime modules/templates are forbidden in both archives. `release_install.py` additionally installs both
archives separately. The workflow action SHAs were resolved through the official
GitHub repositories on 2026-10-16; changes to those pins require review.

Official references:

- [Add a Trusted Publisher to an existing PyPI project](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [Publish with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [PyPA publication action](https://github.com/pypa/gh-action-pypi-publish)
- [Manage GitHub deployment environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
