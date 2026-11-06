"""Build the stable PriceGenerator API reference from the current checkout."""

from pathlib import Path

from pdoc import doc, render

import pricegenerator


OUTPUT = Path(__file__).resolve().parent / "build" / "docs-api" / "pricegenerator.html"


def Main() -> None:
    """Render and verify the root public API before writing generated HTML."""

    # pdoc looks in the module dictionary before trying to import a submodule.
    # Resolve the declared lazy exports so their signatures and docstrings appear.
    for name in pricegenerator.__all__:
        getattr(pricegenerator, name)

    module = doc.Module.from_name("pricegenerator")
    render.configure(docformat="google", show_source=False)
    html = render.html_module(module, {module.modulename: module})
    missing = [name for name in pricegenerator.__all__ if f'id="{name}"' not in html]

    if missing:
        raise RuntimeError(f"API reference omitted public exports: {', '.join(missing)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(html.encode("utf-8"))


if __name__ == "__main__":
    Main()
