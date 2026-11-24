"""Rebuild the Monte Carlo documentation figure and its archive of hourly candles."""

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np

from pricegenerator import ReadCSV
from pricegenerator.rendering import ChartSeries, PrepareChart, RenderSVG


SVG_URI = "http://www.w3.org/2000/svg"
SVG = f"{{{SVG_URI}}}"
REFERENCE = Path(__file__).resolve().parents[1] / "assets" / "pricegenerator-2-2-experiment-quantiles.svg"
MEMBER_COLOR = "#8b9bb3"


def PriceLayers(frame):
    """Select the native grid, candle, volume and overlay elements before the wordmark."""

    children = list(frame)
    grid = frame.find(f"{SVG}path")
    watermark = frame.find(f"{SVG}g[@data-watermark-panel='price']")

    return slice(children.index(grid), children.index(watermark))


def DrawExample(frames):
    """Keep the original release artwork and fit all paths to one native price axis."""

    ET.register_namespace("", SVG_URI)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    reference = ET.parse(REFERENCE).getroot()
    layout = reference.find(f"{SVG}g")
    closes = np.stack([frame["close"].to_numpy() for frame in frames])
    levels = (0.05, 0.50, 0.95)
    members = tuple(
        ChartSeries(f"path-{index:02d}", f"Path {index:02d}", tuple(prices), color=MEMBER_COLOR, width=1.1)
        for index, prices in enumerate(closes[1:], 1)
    )
    quantiles = []

    for level, values in zip(levels, np.quantile(closes, levels, axis=0, method="linear"), strict=True):
        key = f"close-p{level * 100:02.0f}"
        original = layout.find(f".//{SVG}g[@data-series='{key}']")
        quantiles.append(ChartSeries(key, key, tuple(values), color=original.attrib["stroke"], width=2.4))

    spec = PrepareChart(frames[0], title=reference.findtext(f"{SVG}title"), series=(*members, *quantiles))
    native = ET.fromstring(RenderSVG(spec)).find(f"{SVG}g")
    candle_titles = f"{SVG}g[@data-candle-index]/{SVG}title"

    if [node.text for node in native.findall(candle_titles)] != [node.text for node in layout.findall(candle_titles)]:
        raise ValueError("Path 00 must match the timestamps, prices and volume of the release example")

    overlays = native.find(f".//{SVG}g[@data-series='close-p05']/..")
    clip = layout.find(f".//{SVG}g[@data-series='close-p05']/..").attrib["clip-path"]
    overlays.set("clip-path", clip)
    behind = ET.Element(f"{SVG}g", {"data-layer": "member-closes", "clip-path": clip, "opacity": "0.46"})

    for line in list(overlays):
        if line.attrib["data-series"].startswith("path-"):
            overlays.remove(line)
            behind.append(line)

    first_candle = native.find(f"{SVG}g[@data-candle-index='0']")
    native.insert(list(native).index(first_candle), behind)
    layout[PriceLayers(layout)] = list(native)[PriceLayers(native)]
    reference.find(f"{SVG}desc").text = (
        "120 hourly candles and volume bars for path 00. Thin grey lines trace the closing prices "
        "of paths 01–31. Blue, purple and gold show the 5th, 50th and 95th percentiles each hour."
    )
    median_label = layout.find(f"{SVG}text[.='P50 close']")
    key = ET.SubElement(layout, f"{SVG}g", {"transform": f"translate(272 {median_label.attrib['y']})"})
    ET.SubElement(key, f"{SVG}path", {"d": "M 0 -4 H 26", "stroke": MEMBER_COLOR, "stroke-width": "1.1"})
    ET.SubElement(key, f"{SVG}text", {"x": "36", "font-size": "12", "fill": median_label.attrib["fill"]}).text = (
        "Paths 01–31 · hourly closes"
    )
    labels = {
        "P05 close": "P05 · 5th percentile", "P50 close": "P50 · median", "P95 close": "P95 · 95th percentile",
        "Candles and volume: ensemble path 0. Lines or points: close quantiles across all paths.":
            "Candles and volume show path 00. Each thin grey line follows one of the other 31 paths.",
        "P05-P95 is a pointwise synthetic range. Simultaneous path coverage has not been estimated.":
            "The three coloured lines summarize all 32 closing prices at each hour.",
    }

    for label in layout.findall(f"{SVG}text"):
        if label.text in labels:
            label.text = labels[label.text]

    return ET.tostring(reference, encoding="unicode") + "\n"


def Build(source, output):
    """Package the 32 published CSV files and draw their aligned hourly data."""

    files = [source / f"path-{index:02d}.csv" for index in range(32)]
    frames = [ReadCSV(path, timeframe_seconds=3600, allow_gaps=False) for path in files]
    timestamps = frames[0]["datetime"]

    if len(timestamps) != 120 or any(not frame["datetime"].equals(timestamps) for frame in frames):
        raise ValueError("The published example requires 32 paths on the same 120 hourly timestamps")

    figure = DrawExample(frames)
    (output / "monte-carlo-32-paths.svg").write_text(figure, encoding="utf-8", newline="\n")

    with ZipFile(output / "monte-carlo-32-paths.zip", "w") as archive:
        for path in files:
            entry = ZipInfo(path.name)
            entry.create_system = 3
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, path.read_bytes(), compress_type=ZIP_DEFLATED)


def Main():
    """Read the exported example paths and write the corresponding Pages assets."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    Build(args.paths, args.output)


if __name__ == "__main__":
    Main()
