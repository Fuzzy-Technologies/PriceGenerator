"""Validate an exact release ref and the two immutable distribution artifacts."""

import argparse
import ast
import hashlib
import json
import re
import subprocess
import tarfile
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile


class ReleaseError(ValueError):
    """Describe a release invariant that must stop publication."""


def Git(*arguments):
    """Read repository state without invoking a shell."""

    return subprocess.run(["git", *arguments], check=True, capture_output=True, text=True).stdout.strip()


def ReadVersion(path):
    """Read the literal source version without importing the package."""

    tree = ast.parse(Path(path).read_text(encoding="utf-8"))

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__"
                                               for target in node.targets):
            return ast.literal_eval(node.value)

    raise ReleaseError("Canonical version literal is missing")


def CheckRef(tag, version, publish=False):
    """Require a matching version tag at the fetched master and checked-out commit."""

    if not re.fullmatch(r"v[0-9][0-9A-Za-z.!+_-]*", tag):
        raise ReleaseError("Release tag must be v followed by the exact canonical version")

    if tag != f"v{version}":
        raise ReleaseError(f"Release tag {tag!r} does not match source version {version!r}")

    if publish and (".dev" in version or "+" in version):
        raise ReleaseError("Development and local versions cannot be published by this workflow")

    head = Git("rev-parse", "HEAD")
    master = Git("rev-parse", "refs/remotes/origin/master")
    tagged = Git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")

    if head != master or head != tagged:
        raise ReleaseError("Release tag, checked-out commit and origin/master must identify the same exact commit")

    if Git("status", "--porcelain"):
        raise ReleaseError("Source checkout contains tracked changes or nonignored untracked files")

    return head


def CheckArtifacts(directory, version):
    """Verify metadata, license presence and matching source/wheel versions."""

    directory = Path(directory)
    archives = sorted(path for path in directory.iterdir() if path.name != "SHA256SUMS")
    wheels = [path for path in archives if path.suffix == ".whl"]
    sources = [path for path in archives if path.name.endswith(".tar.gz")]

    if len(archives) != 2 or len(wheels) != 1 or len(sources) != 1:
        raise ReleaseError("Release directory must contain exactly one wheel and one sdist")

    with ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]

        if len(metadata_names) != 1 or not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
            raise ReleaseError("Wheel metadata or Apache license is missing")

        wheel_metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))

        if any(name.endswith((".j2", ".py.txt", ".j2.txt", "/PriceGenerator.py", "/UniLogger.py")) for name in names):
            raise ReleaseError("Retired runtime modules and templates must not be shipped")

    with tarfile.open(sources[0]) as archive:
        names = archive.getnames()
        metadata_names = [name for name in names if name.count("/") == 1 and name.endswith("/PKG-INFO")]

        if len(metadata_names) != 1 or not any(name.count("/") == 1 and name.endswith("/LICENSE") for name in names):
            raise ReleaseError("Source metadata or Apache license is missing")

        source_metadata = BytesParser().parsebytes(archive.extractfile(metadata_names[0]).read())

        if any(name.endswith((".j2", ".py.txt", ".j2.txt", "/PriceGenerator.py", "/UniLogger.py")) for name in names):
            raise ReleaseError("Retired runtime modules and templates must not be shipped in the sdist")

    for package_metadata in (wheel_metadata, source_metadata):
        if package_metadata["Name"] != "pricegenerator" or package_metadata["Version"] != version:
            raise ReleaseError("Artifact identity differs from canonical source version")

        python_specs = {item.strip() for item in (package_metadata["Requires-Python"] or "").split(",")}

        if python_specs != {">=3.10", "<3.14"}:
            raise ReleaseError("Artifact Python support differs from the verified matrix")

        requirements = " ".join(package_metadata.get_all("Requires-Dist", [])).lower()

        if any(name in requirements for name in ("bokeh", "jinja2", "pandas-ta", "bkcharts")):
            raise ReleaseError("Artifact metadata contains an obsolete runtime dependency")

    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in archives}


def CheckCI(pages, commit):
    """Require the latest quality and Canvas workflow runs for one exact commit."""

    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ReleaseError("CI evidence requires an exact lowercase 40-character commit SHA")

    if isinstance(pages, dict):
        pages = [pages]

    if not isinstance(pages, list) or not pages:
        raise ReleaseError("CI API response must contain workflow-run pages")

    runs = []

    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("workflow_runs"), list):
            raise ReleaseError("CI API response is missing workflow_runs")

        runs.extend(page["workflow_runs"])

    evidence = {}

    for path in (".github/workflows/ci.yml", ".github/workflows/chart-runtime.yml"):
        candidates = [run for run in runs if isinstance(run, dict) and run.get("path") == path and run.get("head_sha") == commit]

        if not candidates:
            raise ReleaseError(f"Missing CI evidence for {path} at {commit}; run the quality and chart runtime gates first")

        try:
            latest = max(candidates, key=lambda run: (int(run["run_number"]), int(run.get("run_attempt", 1))))

        except (KeyError, TypeError, ValueError) as error:
            raise ReleaseError(f"Malformed CI run identity for {path}") from error

        if latest.get("status") != "completed" or latest.get("conclusion") != "success":
            raise ReleaseError(f"Latest CI run for {path} at {commit} is not completed successfully: "
                               f"{latest.get('status')}/{latest.get('conclusion')}")

        evidence[path] = latest.get("html_url", "success")

    return evidence


def Main():
    """Run read-only release checks and optionally record artifact hashes."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--ci-runs", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--version-file", type=Path, default=Path("pricegenerator/_version.py"))
    arguments = parser.parse_args()
    version = ReadVersion(arguments.version_file)
    evidence = {"version": version}

    if arguments.tag:
        evidence["commit"] = CheckRef(arguments.tag, version, arguments.publish)

    if arguments.ci_runs:
        evidence["ci"] = CheckCI(json.loads(arguments.ci_runs.read_text(encoding="utf-8")), arguments.commit or "")

    if arguments.artifacts:
        hashes = CheckArtifacts(arguments.artifacts, version)
        manifest = "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items()))
        (arguments.artifacts / "SHA256SUMS").write_text(manifest, encoding="utf-8")
        evidence["sha256"] = hashes

    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    Main()
