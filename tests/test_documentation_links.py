"""Check localized documentation validation with isolated Markdown sources."""

from pathlib import Path

import pytest


pytest.importorskip("markdown_it")

from tools.documentation_links import CheckDocumentation, LOCALES  # noqa: E402


def WriteTranslations(root: Path) -> Path:
    """Create matching pages with cross-language navigation."""

    content = root / "docs" / "site" / "content"

    for locale in LOCALES:
        directory = content / locale
        directory.mkdir(parents=True)
        links = [f"[{other}](../{other}/guide.md)" for other in LOCALES if other != locale]
        (directory / "guide.md").write_text(" · ".join(links) + "\n", encoding="utf-8")

    return content


def test_ResolvesMarkdownLinksAndIgnoresCodeAndRemoteDestinations(tmp_path: Path) -> None:
    """Check reference links, images, URL suffixes and fenced examples."""

    content = WriteTranslations(tmp_path)
    (content / "image file.svg").touch()
    page = content / "en" / "guide.md"
    examples = (
        "\n![Figure](../image%20file.svg) [RU again][ru-guide]\n\n"
        "[ru-guide]: ../ru/guide.md?source=docs#example\n\n"
        "[Remote](https://example.com/missing) [Fragment](#local)\n\n"
        "```markdown\n[Example](missing.md)\n```\n"
    )
    page.write_text(page.read_text(encoding="utf-8") + examples, encoding="utf-8")

    assert CheckDocumentation(tmp_path) == [], "Valid localized sources must pass"


def test_ReportsMissingTranslationNavigationAndInvalidTargets(tmp_path: Path) -> None:
    """Fail for missing locales, absent navigation and invalid local paths."""

    content = WriteTranslations(tmp_path)
    (content / "zh-CN" / "guide.md").unlink()
    outside = "../" * len((content / "en").relative_to(tmp_path).parts) + "../guide.md"
    (content / "en" / "guide.md").write_text(
        f"[Missing][ref] [Outside]({outside})\n\n[ref]: no.md\n", encoding="utf-8",
    )
    (content / "ru" / "guide.md").write_text("[EN](../en/guide.md)\n", encoding="utf-8")

    assert CheckDocumentation(tmp_path) == [
        "docs/site/content/en/guide.md: invalid relative target 'no.md'",
        f"docs/site/content/en/guide.md: invalid relative target {outside!r}",
        "docs/site/content/en/guide.md: missing language link to ru",
        "docs/site/content/zh-CN/guide.md: missing translation",
    ], "The gate must report each failing page and destination"


def test_PublicGuidesKeepTheReadersLanguage():
    """Keep PyPI and localized guide navigation on the rendered, matching edition."""

    from urllib.parse import urlsplit

    from markdown_it import MarkdownIt

    root = Path(__file__).resolve().parents[1]
    content = root / "docs" / "site" / "content"
    sources = [*content.glob("*/*.md"), *(root / "docs").glob("release-2-2*.md")]
    pages = {root / "README.md": ("en", "/"), root / "README_RU.md": ("ru", "/ru/")}
    routes = {"/", "/ru/", "/zh-CN/"}
    language_names = {"English", "Русский", "简体中文"}

    for source in sources:
        front = source.read_text(encoding="utf-8").split("---", 2)[1]
        fields = dict(line.split(": ", 1) for line in front.splitlines() if ": " in line)
        lang = fields["lang"]
        route = f"/{lang}/{fields['route']}/"
        assert fields["permalink"] == route and route not in routes, source
        pages[source] = (lang, route)
        routes.add(route)

    parser = MarkdownIt("commonmark").enable("table")

    for page, (lang, route) in pages.items():
        for block in parser.parse(page.read_text(encoding="utf-8")):
            tokens = block.children or []

            for index, token in enumerate(tokens):
                if token.type != "link_open":
                    continue

                url = urlsplit(token.attrGet("href"))
                assert not (url.hostname in ("github.com", "raw.githubusercontent.com") and url.path.endswith(".md")), page

                if url.hostname != "fuzzy-technologies.com" or not url.path.startswith("/PriceGenerator/"):
                    continue

                path = url.path.removeprefix("/PriceGenerator")

                if path.startswith(("/docs/assets/", "/docs/evidence/", "/media/")):
                    assert (root / path.lstrip("/")).is_file(), (page, path)
                    continue

                assert path in routes, (page, path)
                destination_lang = path.strip("/").split("/")[0] or "en"

                if destination_lang != lang:
                    assert tokens[index + 1].content in language_names, (page, path)
                    assert path.split("/")[2:] == route.split("/")[2:] or path in ("/", "/ru/", "/zh-CN/"), (page, path)
