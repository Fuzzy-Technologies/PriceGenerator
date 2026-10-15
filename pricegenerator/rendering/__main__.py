"""Render existing CSV prices through an explicit, offline chart command."""

import argparse
from pathlib import Path

from .adapters import FromDataFrame, SaveMarkdown, _Pandas


def _SameFile(first: Path, second: Path) -> bool:
    """Treat existing hard links as the same file, in addition to resolved paths."""

    return first == second or (first.exists() and second.exists() and first.samefile(second))


def Main(argv: list[str] | None = None) -> int:
    """Read requested inputs and write only explicitly selected chart outputs."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="CSV with datetime,open,high,low,close,volume headers.")
    parser.add_argument("--legacy-csv", action="store_true", help="Read headerless date,time,OHLCV CSV instead.")
    parser.add_argument("--timezone", help="Explicit timezone for naive timestamps, for example UTC or Europe/Moscow.")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter; defaults to comma.")
    parser.add_argument("--svg", type=Path, help="Write an offline SVG chart.")
    parser.add_argument("--html", type=Path, help="Write a standalone offline interactive HTML chart.")
    parser.add_argument("--report", type=Path, help="Write the supplied chart summary as Markdown.")
    parser.add_argument("--summary", action="append", default=[], help="Plain-text summary line; repeat to add lines.")
    parser.add_argument("--markers", type=Path, help="CSV with datetime and markersUpper/markersCenter/markersLower columns.")
    parser.add_argument("--line", type=Path, action="append", default=[], help="CSV with datetime and named numeric series; may repeat.")
    parser.add_argument("--title", default="PriceGenerator")
    parser.add_argument("--theme", choices=("dark", "light"), default="dark")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=760)
    parser.add_argument("--precision", type=int, default=2)
    parser.add_argument("--hide-controls", action="store_true")
    arguments = parser.parse_args(argv)

    if not arguments.svg and not arguments.html:
        parser.error("choose at least one chart output with --svg or --html")

    paths = [arguments.input, arguments.markers, *arguments.line]
    inputs = {path.resolve() for path in paths if path is not None}
    outputs = [path.resolve() for path in (arguments.svg, arguments.html, arguments.report) if path is not None]

    if any(_SameFile(output, source) for output in outputs for source in inputs) or any(
        _SameFile(output, previous) for index, output in enumerate(outputs) for previous in outputs[:index]
    ):
        parser.error("output paths must be distinct and must not overwrite any input")

    pandas = _Pandas()

    try:
        if arguments.legacy_csv:
            frame = pandas.read_csv(arguments.input, sep=arguments.delimiter, header=None, names=("date", "time", "open", "high", "low", "close", "volume"))
            frame["datetime"] = frame["date"].astype(str).str.replace(".", "-", regex=False) + "T" + frame["time"].astype(str)

        else:
            frame = pandas.read_csv(arguments.input, sep=arguments.delimiter)

        markers = None if arguments.markers is None else pandas.read_csv(arguments.markers, sep=arguments.delimiter, keep_default_na=False, dtype=str)
        lines = [pandas.read_csv(path, sep=arguments.delimiter) for path in arguments.line]
        summary = tuple(arguments.summary) or (f"- Candles count: {len(frame)}", "- Raw OHLCV chart; no indicator calculations were requested.")
        spec = FromDataFrame(
            frame, assume_timezone=arguments.timezone, markers=markers, lines=lines, summary=summary,
            title=arguments.title, theme=arguments.theme, width=arguments.width, height=arguments.height,
            price_precision=arguments.precision, show_controls=not arguments.hide_controls,
        )

    except (ValueError, TypeError, KeyError) as error:
        parser.error(str(error))

    if arguments.svg is not None:
        from .static import SaveSVG

        SaveSVG(spec, arguments.svg)

    if arguments.html is not None:
        from .interactive import SaveInteractive

        SaveInteractive(spec, arguments.html)

    if arguments.report is not None:
        SaveMarkdown(spec, arguments.report)

    return 0


if __name__ == "__main__":
    raise SystemExit(Main())
