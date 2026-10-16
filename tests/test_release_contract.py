"""Test release authorization and artifact rejection without production services."""

import io
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools import release_verify


@pytest.mark.parametrize("tag", ["master", "v2.0.0;touch /tmp/no", "v2.0.1", "--help"])
def test_RejectInvalidOrMismatchedTagsBeforeGit(tag, monkeypatch):
    """Reject untrusted ref input before executing any Git command."""

    def RejectGit(*arguments):
        """Fail if invalid user input reaches Git."""

        pytest.fail(f"Invalid release input reached Git: {arguments}")

    monkeypatch.setattr(release_verify, "Git", RejectGit)

    with pytest.raises(release_verify.ReleaseError, match="tag"):
        release_verify.CheckRef(tag, "2.0.0")


@pytest.mark.parametrize("version", ["2.0.0.dev0", "2.0.0+local"])
def test_RejectUnreleasedPublication(version):
    """Prevent the release workflow from publishing development or local versions."""

    with pytest.raises(release_verify.ReleaseError, match="cannot be published"):
        release_verify.CheckRef(f"v{version}", version, publish=True)


@pytest.mark.parametrize("master,tagged,dirty", [("other", "head", ""), ("head", "other", ""), ("head", "head", " M file"), ("head", "head", "?? accidental.py")])
def test_RejectMovedBranchTagAndDirtySource(master, tagged, dirty, monkeypatch):
    """Stop release when the reviewed source identity changes."""

    def FakeGit(*arguments):
        """Return deterministic local repository identities."""

        values = {("rev-parse", "HEAD"): "head", ("rev-parse", "refs/remotes/origin/master"): master,
                  ("rev-parse", "--verify", "refs/tags/v2.0.0^{commit}"): tagged,
                  ("status", "--porcelain"): dirty}

        return values[arguments]

    monkeypatch.setattr(release_verify, "Git", FakeGit)

    with pytest.raises(release_verify.ReleaseError):
        release_verify.CheckRef("v2.0.0", "2.0.0", publish=True)


def MakeArtifacts(directory, version="2.0.0", obsolete=False, license_present=True, requires_python=">=3.10,<3.14"):
    """Construct small real archives for deterministic metadata rejection tests."""

    identity = f"Name: pricegenerator\nVersion: {version}\nRequires-Python: {requires_python}\n"

    if obsolete:
        identity += "Requires-Dist: bokeh>=3\n"

    with ZipFile(directory / "pricegenerator-2.0.0-py3-none-any.whl", "w") as archive:
        archive.writestr("pricegenerator-2.0.0.dist-info/METADATA", identity)

        if license_present:
            archive.writestr("pricegenerator-2.0.0.dist-info/licenses/LICENSE", "Apache-2.0")

    with tarfile.open(directory / "pricegenerator-2.0.0.tar.gz", "w:gz") as archive:
        for name, content in (("PKG-INFO", identity), ("LICENSE", "Apache-2.0")):
            data = content.encode()
            entry = tarfile.TarInfo(f"pricegenerator-2.0.0/{name}")
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))


def test_AcceptExactArtifactPairAndHashEveryByte(tmp_path):
    """Produce hashes for the actual wheel and sdist files presented for review."""

    MakeArtifacts(tmp_path)
    hashes = release_verify.CheckArtifacts(tmp_path, "2.0.0")
    assert len(hashes) == 2, "Every release artifact must have its own digest"
    assert all(len(digest) == 64 for digest in hashes.values()), "Artifact digest must be SHA-256"
    assert release_verify.ReadVersion(Path(__file__).parents[1] / "pricegenerator/_version.py"), "Version literal missing"


@pytest.mark.parametrize("options,reason", [
    ({"version": "9.9.9"}, "identity"), ({"obsolete": True}, "obsolete"), ({"license_present": False}, "license"),
])
def test_RejectUnreviewedMetadata(tmp_path, options, reason):
    """Reject wrong identity, retired dependencies and omitted licensing."""

    MakeArtifacts(tmp_path, **options)

    with pytest.raises(release_verify.ReleaseError, match=reason):
        release_verify.CheckArtifacts(tmp_path, "2.0.0")


def test_RejectUnexpectedReleasePayload(tmp_path):
    """Prevent unrelated files from entering the publisher distribution set."""

    MakeArtifacts(tmp_path)
    (tmp_path / "unexpected.txt").write_text("unreviewed", encoding="utf-8")

    with pytest.raises(release_verify.ReleaseError, match="exactly one"):
        release_verify.CheckArtifacts(tmp_path, "2.0.0")


def test_CommandFailurePropagatesWithoutImportOverrides(tmp_path, monkeypatch):
    """Pass only sanitized process state and fail immediately on command errors."""

    import subprocess

    from tools import release_install

    monkeypatch.setenv("PYTHONPATH", "untrusted-checkout")
    monkeypatch.setenv("PYTHONHOME", "untrusted-runtime")
    observed = {}

    def FailCommand(arguments, **options):
        """Record invocation options and model a failing installer."""

        observed.update(options)
        raise subprocess.CalledProcessError(1, arguments)

    monkeypatch.setattr(release_install.subprocess, "run", FailCommand)

    with pytest.raises(subprocess.CalledProcessError):
        release_install.Run(["python", "--version"], tmp_path)

    assert "PYTHONPATH" not in observed["env"] and "PYTHONHOME" not in observed["env"], "Import override leaked"
    assert observed["check"] is True, "Installer failure must stop verification"
    assert observed["cwd"] == tmp_path, "Verification left its isolated directory"


def test_ArtifactFailureCleansTemporaryEnvironment(tmp_path, monkeypatch):
    """Remove isolated environments after a smoke failure and stop optional installation."""

    from tools import release_install

    commands = []
    directories = []

    def FakeCreate(self, directory):
        """Create only a filesystem marker rather than an actual environment."""

        directory.mkdir()
        directories.append(directory.parent)

    def FailSmoke(arguments, directory):
        """Allow core installation then fail its behavioral verification."""

        commands.append(arguments)

        if len(commands) == 2:
            raise RuntimeError("deterministic smoke failure")

    monkeypatch.setattr(release_install.venv.EnvBuilder, "create", FakeCreate)
    monkeypatch.setattr(release_install, "Run", FailSmoke)

    with pytest.raises(RuntimeError, match="smoke failure"):
        release_install.Verify(tmp_path / "candidate.whl")

    assert len(commands) == 2, "Verification continued after core smoke failure"
    assert directories and not directories[0].exists(), "Failed verification leaked its temporary environment"


@pytest.mark.parametrize("retired", [
    "pricegenerator/PriceGenerator.py", "pricegenerator/UniLogger.py", "pricegenerator/template.j2",
    "docs/legacy.py.txt", "docs/template.j2.txt",
])
def test_RejectRetiredSourceEvenWhenWheelIsClean(tmp_path, retired):
    """Do not publish removed runtime code hidden only in the source archive."""

    MakeArtifacts(tmp_path)
    source = tmp_path / "pricegenerator-2.0.0.tar.gz"
    temporary = tmp_path / "replacement.tar.gz"

    with tarfile.open(source) as original, tarfile.open(temporary, "w:gz") as replacement:
        for member in original.getmembers():
            replacement.addfile(member, original.extractfile(member))

        payload = b"retired source"
        member = tarfile.TarInfo(f"pricegenerator-2.0.0/{retired}")
        member.size = len(payload)
        replacement.addfile(member, io.BytesIO(payload))

    temporary.replace(source)

    with pytest.raises(release_verify.ReleaseError, match="Retired.*sdist"):
        release_verify.CheckArtifacts(tmp_path, "2.0.0")


def CIRun(path, *, commit="a" * 40, number=1, status="completed", conclusion="success"):
    """Provide an Actions API record without contacting hosted infrastructure."""

    return {"path": f".github/workflows/{path}", "head_sha": commit, "run_number": number,
            "run_attempt": 1, "status": status, "conclusion": conclusion, "html_url": "https://example.invalid/run"}


def test_AcceptExactGreenQualityAndCanvasEvidence():
    """Require actual successful workflow conclusions matching the tagged commit."""

    pages = [{"workflow_runs": [CIRun("ci.yml")]}, {"workflow_runs": [CIRun("chart-runtime.yml")]}]
    evidence = release_verify.CheckCI(pages, "a" * 40)
    assert set(evidence) == {".github/workflows/ci.yml", ".github/workflows/chart-runtime.yml"}, "A required gate was omitted"


@pytest.mark.parametrize("status,conclusion", [
    ("queued", None), ("in_progress", None), ("waiting", None), ("unknown", "success"),
    ("completed", "failure"), ("completed", "cancelled"), ("completed", "skipped"), ("completed", None),
])
def test_RejectPendingFailedAndUnknownLatestCI(status, conclusion):
    """An older green run cannot hide the latest unfinished or failed verification."""

    runs = [CIRun("ci.yml"), CIRun("chart-runtime.yml"), CIRun("ci.yml", number=2, status=status, conclusion=conclusion)]

    with pytest.raises(release_verify.ReleaseError, match="not completed successfully"):
        release_verify.CheckCI({"workflow_runs": runs}, "a" * 40)


@pytest.mark.parametrize("runs", [[], [CIRun("ci.yml")],
                                      [CIRun("ci.yml"), CIRun("chart-runtime.yml", commit="b" * 40)]])
def test_RejectMissingAndWrongCommitCI(runs):
    """Do not substitute a workflow success from another commit or another gate."""

    with pytest.raises(release_verify.ReleaseError, match="Missing CI evidence"):
        release_verify.CheckCI({"workflow_runs": runs}, "a" * 40)


@pytest.mark.parametrize("response", [[], None, {}, [{"workflow_runs": None}], {"workflow_runs": [CIRun("ci.yml", number=None)]}])
def test_RejectMalformedCIResponse(response):
    """Fail closed when the API evidence is missing or has unsupported fields."""

    with pytest.raises(release_verify.ReleaseError):
        release_verify.CheckCI(response, "a" * 40)


def test_AcceptBuildBackendNormalizedPythonSpecifierOrder(tmp_path):
    """Setuptools canonical ordering must not reject the declared runtime window."""

    MakeArtifacts(tmp_path, requires_python="<3.14,>=3.10")
    assert len(release_verify.CheckArtifacts(tmp_path, "2.0.0")) == 2, "Normalized equivalent metadata was rejected"


@pytest.mark.parametrize("requires_python", [">=3.9,<3.14", ">=3.10", ">=3.10,<3.15", ""])
def test_RejectDifferentOrMissingPythonWindow(tmp_path, requires_python):
    """Order-independent comparison must still reject unsupported runtime promises."""

    MakeArtifacts(tmp_path, requires_python=requires_python)

    with pytest.raises(release_verify.ReleaseError, match="Python support"):
        release_verify.CheckArtifacts(tmp_path, "2.0.0")
