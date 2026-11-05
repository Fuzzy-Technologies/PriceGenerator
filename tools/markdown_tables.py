# SPDX-FileCopyrightText: 2026 Timur Gilmullin and Fuzzy Technologies
# SPDX-License-Identifier: Apache-2.0

"""Align authored Markdown tables without changing cells or literal code examples."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from collections.abc import Sequence
from pathlib import Path

SEPARATOR_CELL = re.compile(r":?-{3,}:?\Z")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def SplitRow(line: str) -> list[str] | None:
    """Split cells at unescaped pipes, including pipes inside inline code.

    Args:
        line: One Markdown source line with optional outer pipes.

    Returns:
        Trimmed cell contents, or None when no pipe-delimited row is present.

    """

    stripped = line.strip()

    if "|" not in stripped:
        return None

    cells: list[str] = []
    start = 1 if stripped.startswith("|") else 0
    index = start

    while index < len(stripped):
        character = stripped[index]

        if character == "\\":
            index += 2
            continue

        if character == "|":
            cells.append(stripped[start:index].strip())
            start = index + 1

        index += 1

    if start < len(stripped):
        cells.append(stripped[start:].strip())

    return cells if cells else None


def IndentedCode(line: str) -> bool:
    """Recognize a four-column indentation boundary before table detection.

    Args:
        line: Source line whose leading spaces and tabs are inspected.

    Returns:
        Whether indentation denotes literal code, with four-column tab stops.

    """

    prefix = line[:len(line) - len(line.lstrip(" \t"))]

    return len(prefix.expandtabs(4)) >= 4


def CellWidth(cell: str) -> int:
    """Count source display columns, including wide glyphs and combining marks."""

    return sum(
        2 if unicodedata.east_asian_width(character) in {"F", "W"} else 1
        for character in cell
        if unicodedata.category(character) not in {"Mn", "Me", "Cf"}
    )


def AlignMarkdown(text: str) -> str:
    """Pad valid table columns and separator rules to their complete cell widths.

    Args:
        text: Markdown source, including its original line endings.

    Returns:
        Canonical table padding with unchanged cells, alignment markers, literal
        code, other source text, line endings, and final-newline presence.

    """

    lines = text.splitlines(keepends=True)
    index = 0
    fence: tuple[str, int] | None = None

    while index < len(lines):
        match = FENCE.match(lines[index])

        if match:
            marker = match.group(1)

            if fence is None:
                fence = (marker[0], len(marker))

            elif (
                marker[0] == fence[0] and len(marker) >= fence[1]
                and not lines[index][match.end():].strip()
            ):
                fence = None

            index += 1
            continue

        if fence or index + 1 >= len(lines) or IndentedCode(lines[index]):
            index += 1
            continue

        if IndentedCode(lines[index + 1]):
            index += 1
            continue

        header = SplitRow(lines[index])
        separator = SplitRow(lines[index + 1])

        if not header or not separator or len(header) != len(separator) or not all(
            SEPARATOR_CELL.fullmatch(cell) for cell in separator
        ):
            index += 1
            continue

        rows = [header, separator]
        end = index + 2

        while end < len(lines):
            if IndentedCode(lines[end]):
                break

            row = SplitRow(lines[end])

            if row is None or len(row) != len(header):
                break

            rows.append(row)
            end += 1

        widths = [max(3 + separator[column].count(":"),
                      *(CellWidth(row[column]) for offset, row in enumerate(rows) if offset != 1))
                  for column in range(len(header))]

        for offset, row in enumerate(rows):
            rendered = []

            for column, cell in enumerate(row):
                if offset == 1:
                    left = ":" if cell.startswith(":") else ""
                    right = ":" if cell.endswith(":") else ""
                    cell = left + "-" * (widths[column] - len(left) - len(right)) + right

                rendered.append(cell + " " * (widths[column] - CellWidth(cell)))

            original = lines[index + offset]
            prefix = original[:len(original) - len(original.lstrip())]
            newline = ""

            if original.endswith("\r\n"):
                newline = "\r\n"

            elif original.endswith(("\n", "\r")):
                newline = original[-1]

            lines[index + offset] = prefix + "| " + " | ".join(rendered) + " |" + newline

        index = end

    return "".join(lines)


def TrackedMarkdown(project_root: Path) -> tuple[Path, ...]:
    """List regular tracked Markdown files, excluding untracked generated output.

    Args:
        project_root: Git checkout whose index determines the formatter's scope.

    Returns:
        Tracked Markdown paths in Git's deterministic index order.

    Raises:
        ValueError: A tracked path is unresolved, symbolic, or not a regular file.
        subprocess.CalledProcessError: The root is not an available Git checkout.

    """

    project_root = project_root.absolute()
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z", "--", "*.md"], cwd=project_root,
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    paths = []

    for entry in result.stdout.split("\0"):
        if not entry:
            continue

        metadata, name = entry.split("\t", 1)
        mode, _, stage = metadata.split()
        path = project_root / name

        if mode not in {"100644", "100755"} or stage != "0":
            raise ValueError(f"{name}: Markdown formatting requires a regular, resolved Git entry")

        for component in (path, *path.parents):
            if component.is_symlink():
                raise ValueError(f"{name}: Markdown formatting cannot follow symbolic links")

            if component == project_root:
                break

        if not path.is_file():
            raise ValueError(f"{name}: Tracked Markdown is not an available regular file")

        paths.append(path)

    return tuple(paths)


def ReadMarkdown(path: Path) -> str:
    """Read UTF-8 Markdown without translating its line endings.

    Args:
        path: Regular tracked source file selected by TrackedMarkdown.

    Returns:
        Original text, retaining CRLF, LF, and final-newline presence.

    """

    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read()


def CheckMarkdownTables(project_root: Path) -> tuple[str, ...]:
    """Report tracked files whose table columns drift from readable source alignment.

    Args:
        project_root: Git checkout to inspect without modifying source files.

    Returns:
        Repository-relative diagnostics; an empty tuple means alignment passes.

    """

    project_root = project_root.absolute()
    diagnostics = []

    for path in TrackedMarkdown(project_root):
        text = ReadMarkdown(path)

        if AlignMarkdown(text) != text:
            diagnostics.append(
                f"{path.relative_to(project_root)}: Markdown table columns need alignment"
            )

    return tuple(diagnostics)


def Main(arguments: Sequence[str] | None = None) -> int:
    """Check alignment by default or apply requested table padding and separator rules.

    Args:
        arguments: CLI arguments, or None to read the process argument vector.

    Returns:
        Zero for aligned source; one for drift or unavailable/unsupported files.
        Only an explicit --write changes regular tracked Markdown files.

    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write", action="store_true", help="Apply table alignment locally")
    options = parser.parse_args(arguments)
    project_root = options.project_root.absolute()

    try:
        if options.write:
            for path in TrackedMarkdown(project_root):
                text = ReadMarkdown(path)
                aligned = AlignMarkdown(text)

                if aligned != text:
                    with path.open("w", encoding="utf-8", newline="") as stream:
                        stream.write(aligned)

                    print(path.relative_to(project_root))

        diagnostics = CheckMarkdownTables(project_root)

    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Markdown table alignment: ERROR: {error}", file=sys.stderr)

        return 1

    if diagnostics:
        print("\n".join(diagnostics))
        print("Run python tools/markdown_tables.py --write to align tracked tables.")

        return 1

    print("Markdown table alignment: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(Main())
