"""Check localized documentation coverage, navigation and relative file links."""

from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt


ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "ru", "zh-CN")


def RelativeTargets(parser: MarkdownIt, page: Path) -> Iterator[tuple[str, str, bool]]:
    """Yield relative Markdown link and image paths with navigation eligibility."""

    for block in parser.parse(page.read_text(encoding="utf-8")):
        for token in block.children or ():
            if token.type == "link_open":
                destination = token.attrGet("href")

            elif token.type == "image":
                destination = token.attrGet("src")

            else:
                continue

            if not destination:
                continue

            url = urlsplit(destination)

            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                continue

            yield destination, unquote(url.path), token.type == "link_open"


def CheckDocumentation(root: Path) -> list[str]:
    """Report missing translations, language links and relative targets."""

    root = root.resolve()
    content = root / "docs" / "site" / "content"
    locale_paths = {locale: content / locale for locale in LOCALES}
    routes = {
        page.relative_to(locale_path)
        for locale_path in locale_paths.values()
        for page in locale_path.rglob("*.md")
    }

    if not routes:
        return ["docs/site/content: no localized Markdown pages"]

    parser = MarkdownIt("commonmark").enable("table")
    problems = []

    for route in sorted(routes):
        counterparts = {locale: path / route for locale, path in locale_paths.items()}

        for locale, page in counterparts.items():
            location = page.relative_to(root).as_posix()

            if not page.is_file():
                problems.append(f"{location}: missing translation")
                continue

            navigation = set()

            for destination, path, is_link in RelativeTargets(parser, page):
                target = (page.parent / path).resolve()

                if not target.is_relative_to(root) or not target.exists():
                    problems.append(f"{location}: invalid relative target {destination!r}")

                elif is_link:
                    navigation.add(target)

            for other, counterpart in counterparts.items():
                if other != locale and counterpart.is_file() and counterpart not in navigation:
                    problems.append(f"{location}: missing language link to {other}")

    return problems


def Main() -> int:
    """Print deterministic diagnostics and fail the gate if any check fails."""

    problems = CheckDocumentation(ROOT)

    for problem in problems:
        print(problem)

    if problems:
        return 1

    print("Localized documentation coverage, navigation and relative targets passed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(Main())
