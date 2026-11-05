"""Check the Markdown gate and preservation of literal source content."""

import subprocess

from tools.markdown_tables import AlignMarkdown, Main


def test_TableGateRejectsTrackedDriftUntilFormatted(tmp_path, capsys):
    """Require readable source columns without touching untracked output."""

    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    source = "| Key | Longer heading |\n| --- | ---: |\n| value | 42 |\n"
    page = tmp_path / "README.md"
    page.write_text(source, encoding="utf-8")
    subprocess.run(["git", "add", "--", "README.md"], cwd=tmp_path, check=True)
    preview = tmp_path / "generated.md"
    preview.write_text(source, encoding="utf-8")
    options = ["--project-root", str(tmp_path)]

    assert Main(options) == 1, "Tracked table drift must fail the gate"
    assert "README.md: Markdown table columns need alignment" in capsys.readouterr().out
    assert page.read_text(encoding="utf-8") == source, "Check mode must not rewrite files"

    assert Main([*options, "--write"]) == 0, "Write mode must fix tracked table drift"
    assert Main(options) == 0, "The formatted table must pass on a fresh check"
    assert preview.read_text(encoding="utf-8") == source, "Untracked output must remain untouched"


def test_AlignmentPreservesFencesEscapedPipesAndLineEndings():
    """Keep fenced examples and cell text intact while aligning real tables."""

    table = "| Term | Description |\r\n| --- | ---: |\r\n| `x\\|y` | Example |"
    example = f"\x60\x60\x60\x60markdown\r\n\x60\x60\x60\r\n{table}\r\n\x60\x60\x60\x60\r\n\r\n"
    aligned = AlignMarkdown(example + table)

    assert aligned.startswith(example), "Literal fenced examples must remain byte-identical"
    assert aligned[len(example):] == (
        "| Term   | Description |\r\n| ------ | ----------: |\r\n| `x\\|y` | Example     |"
    ), "Alignment must preserve the escaped pipe, alignment marker and CRLF"
    assert AlignMarkdown(aligned) == aligned, "Repeated formatting must be idempotent"
