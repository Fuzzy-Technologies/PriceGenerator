"""Check the published reference as a reader sees it after a Jekyll build."""

from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from api_reference import LOCALES, ROOT, VERSION


ORIGIN = "https://fuzzy-technologies.com"
BASE = "/PriceGenerator"


class Page(HTMLParser):
    """Collect link destinations, anchors, locale switches and visible term descriptions."""

    def __init__(self, path: Path) -> None:
        """Read one rendered document."""
        super().__init__(convert_charrefs=True)
        self.ids = Counter()
        self.links = []
        self.locales = {}
        self.language = ""
        self.definitions = []
        self.canonical = ""
        self.descriptions = []
        self._active_text = None
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Collect attributes that form the public navigation contract."""
        values = dict(attrs)
        if "id" in values:
            self.ids[values["id"]] += 1
        if tag == "a":
            self.links.append(values.get("href", ""))
            if "data-locale" in values:
                self.locales[values["data-locale"]] = values["href"]
        elif tag == "link" and values.get("rel") == "canonical":
            self.canonical = values["href"]
        elif tag == "html":
            self.language = values.get("lang", "")
        elif tag == "dd":
            self._active_text = self.definitions
            self.definitions.append("")
        elif tag == "p" and values.get("class") == "api-description":
            self._active_text = self.descriptions
            self.descriptions.append("")

    def handle_endtag(self, tag: str) -> None:
        """Finish a term description."""
        if tag in ("dd", "p"):
            self._active_text = None

    def handle_data(self, data: str) -> None:
        """Record term text independently of markup."""
        if self._active_text is not None:
            self._active_text[-1] += data


def CheckSite(site: Path) -> None:
    """Check all locale surfaces and resolve every link and fragment on each reference page."""
    cache = {}

    def Read(route: str) -> Page:
        if route not in cache:
            path = site / unquote(route).removeprefix(BASE).lstrip("/")
            if path.is_dir():
                path /= "index.html"
            cache[route] = Page(path)
        return cache[route]

    catalog = json.loads((ROOT / "_data/api_2_2_1.json").read_text(encoding="utf-8"))
    seen_links = set()
    pages = 0
    for language in LOCALES:
        root = f"{BASE}/api/{VERSION}/{language.lower()}/"
        for topic in ["", *catalog["topics"]]:
            suffix = topic + "/" if topic else ""
            route = root + suffix
            page = Read(route)
            assert page.canonical == ORIGIN + route and page.language == language, route
            assert set(page.locales) == set(LOCALES), route
            assert all(page.locales[lang] == f"{BASE}/api/{VERSION}/{lang.lower()}/{suffix}"
                       for lang in LOCALES), route
            assert Read(route.replace(f"/api/{VERSION}/", "/api/latest/")).canonical == ORIGIN + route, route
            assert not [key for key, count in page.ids.items() if count > 1], route
            expected_summaries = sum(1 + len(m["entries"]) for m in catalog["modules"].values() if m["topic"] == topic)
            assert len(page.descriptions) == expected_summaries, route
            assert all(value.strip() for value in page.definitions + page.descriptions), f"Missing translation in {route}"
            for group in catalog["topics"]:
                assert root + group + "/" in page.links, f"Missing {group} in {route}"
            for mod, module in catalog["modules"].items():
                if module["topic"] == topic:
                    keys = [entry["key"] for entry in module["entries"]]
                    keys.extend(mod + "." + const["name"] for const in module["constants"])
                    assert all(key in page.ids for key in keys), f"Missing declaration in {route} ({mod})"
            for link in page.links:
                target = urlsplit(urljoin(ORIGIN + route, link))
                if target.netloc == "fuzzy-technologies.com" and target.path.startswith(BASE + "/"):
                    seen_links.add((target.path, target.fragment))
            pages += 1

    for route, fragment in sorted(seen_links):
        target = Read(route)
        if fragment:
            assert unquote(fragment) in target.ids, f"Broken target: {route}#{fragment}"
    print(f"Verified {pages} reference pages and {len(seen_links)} distinct internal link destinations.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path, help="Jekyll destination directory")
    CheckSite(parser.parse_args().site)
