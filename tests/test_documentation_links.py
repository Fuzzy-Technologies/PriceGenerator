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
