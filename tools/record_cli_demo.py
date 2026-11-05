"""Record a split-pane GIF from the installed PriceGenerator CLI and renderer."""

import argparse
import csv
import hashlib
import io
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from importlib.metadata import version
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from resvg_py import svg_to_bytes


SIZE = (1264, 660)
CHART_SIZE = (790, 460)
CHART_ORIGIN = (447, 165)
COMMANDS = (
    ("pricegenerator generate --seed 42 \\", "  --horizon 120 --output prices.csv \\", "  --manifest scenario.json"),
    ("pricegenerator chart prices.csv \\", "  --output chart.png --width 790 \\", "  --height 460 --no-view"),
    ("pricegenerator replay scenario.json \\", "  --output replay.csv"),
    ("cmp prices.csv replay.csv",),
)
PHASES = ("01  GENERATE", "02  RENDER", "03  REPLAY", "03  REPLAY", "REPLAY VERIFIED")
COLORS = {
    "background": "#090F1A",
    "panel": "#0D1625",
    "border": "#25364D",
    "text": "#EAF2FD",
    "muted": "#9AAFC9",
    "cyan": "#55EBE0",
    "gold": "#F7CC79",
    "lavender": "#CAB2FB",
}


def Capture(directory):
    """Run the displayed CLI, verify replay bytes and prepare a chart reveal."""

    for index, lines in enumerate(COMMANDS[:3]):
        command = shlex.split(" ".join(line.removesuffix("\\") for line in lines))
        cli = [sys.executable, "-I", "-m", command[0], *command[1:]]
        subprocess.run(cli, cwd=directory, check=True)

        if index == 1:
            svg_cli = ["chart.svg" if part == "chart.png" else part for part in cli]
            subprocess.run(svg_cli, cwd=directory, check=True)

    prices = (directory / "prices.csv").read_bytes()
    replay = (directory / "replay.csv").read_bytes()

    if prices != replay:
        raise ValueError("Replay did not reproduce the generated CSV")

    candles = list(csv.DictReader(io.StringIO(prices.decode("utf-8"))))

    if len(candles) != 120:
        raise ValueError("The demo must display exactly 120 OHLCV candles")

    svg = ET.parse(directory / "chart.svg").getroot()
    removed = 0

    for element in svg.iter():
        for child in list(element):
            if "data-candle-index" in child.attrib or "data-volume-index" in child.attrib:
                element.remove(child)
                removed += 1

    if removed != 2 * len(candles):
        raise ValueError("The chart must contain one candle and volume bar per input row")

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    blank_svg = ET.tostring(svg, encoding="unicode")

    with Image.open(io.BytesIO(svg_to_bytes(svg_string=blank_svg))) as empty:
        blank = empty.convert("RGB")

    with Image.open(directory / "chart.png") as actual:
        chart = actual.convert("RGB")

    if blank.size != CHART_SIZE or chart.size != CHART_SIZE:
        raise ValueError("The renderer output does not fit the fixed demo layout")

    return chart, blank, hashlib.sha256(prices).hexdigest()


def Frame(base, fonts, chart, blank, digest, phase, typed=None, reveal=None):
    """Composite the active command and the chart over the fixed shell layout."""

    frame = base.copy()
    draw = ImageDraw.Draw(frame)
    mono, small, heading = fonts
    draw.rounded_rectangle((1016, 41, 1237, 75), radius=17, fill="#102A32", outline="#30616A")
    draw.text((1126, 58), PHASES[phase], font=small, fill=COLORS["cyan"], anchor="mm")

    if reveal is not None:
        frame.paste(blank, CHART_ORIGIN)
        frame.paste(chart.crop((0, 0, reveal, CHART_SIZE[1])), CHART_ORIGIN)

    else:
        draw.line((616, 363, 1065, 363), fill=COLORS["border"], width=1)
        draw.line((840, 279, 840, 454), fill=COLORS["border"], width=1)
        draw.rounded_rectangle((674, 327, 1009, 398), radius=15, fill=COLORS["panel"], outline=COLORS["border"])
        message = "Waiting for a scenario" if phase == 0 else "120 candles ready to render"
        draw.text((842, 352), message, font=heading, fill=COLORS["text"], anchor="mm")
        draw.text((842, 378), "Deterministic OHLCV  /  seed 42", font=small, fill=COLORS["muted"], anchor="mm")

    y = 189

    for index, lines in enumerate(COMMANDS):
        if index > phase:
            break

        offset = typed if index == phase else None

        for line_index, line in enumerate(lines):
            segment = line if offset is None else line[:offset]
            x = 61

            if line_index == 0:
                draw.text((42, y), "$", font=mono, fill=COLORS["cyan"])

            draw.text((x, y), segment, font=mono, fill=COLORS["text"])

            if offset is not None:
                if offset <= len(line):
                    caret = round(x + mono.getlength(segment)) + 1
                    draw.rectangle((caret, y + 2, caret + 5, y + 17), fill=COLORS["gold"])

                    break

                offset -= len(line)

            y += 24

        if index == phase:
            break

        result = {
            0: "120 UTC rows  /  scenario.json",
            1: "chart.png  /  native PNG export",
            3: "Replay matched byte for byte",
        }.get(index)

        if result:
            draw.rounded_rectangle((42, y + 3, 49, y + 10), radius=3, fill=COLORS["cyan"])
            draw.text((58, y - 1), result, font=small, fill=COLORS["cyan"])
            y += 34

    if phase == 4:
        draw.text((42, 587), f"CSV SHA-256  {digest[:20]}…", font=small, fill=COLORS["muted"])

    return frame


def Layout():
    """Draw the permanent labels and panels once for all animation frames."""

    font_root = Path("/usr/share/fonts/truetype/dejavu")
    mono_path = font_root / "DejaVuSansMono.ttf"
    sans_path = font_root / "DejaVuSans.ttf"
    bold_path = font_root / "DejaVuSans-Bold.ttf"
    mono = ImageFont.truetype(str(mono_path), 15)
    small = ImageFont.truetype(str(mono_path), 13)
    heading = ImageFont.truetype(str(bold_path), 19)
    base = Image.new("RGB", SIZE, COLORS["background"])
    draw = ImageDraw.Draw(base)
    draw.rectangle((0, 0, 1263, 3), fill="#1A283C")
    draw.rectangle((0, 0, 310, 3), fill="#54D9D4")
    draw.text((25, 24), "PriceGenerator", font=ImageFont.truetype(str(bold_path), 43), fill=COLORS["text"])
    draw.text(
        (28, 85), "Generate a scenario, export a chart, and replay the same data.",
        font=ImageFont.truetype(str(sans_path), 18), fill=COLORS["muted"],
    )
    draw.rounded_rectangle((24, 127, 430, 626), radius=12, fill=COLORS["panel"], outline=COLORS["border"])
    draw.rounded_rectangle((446, 127, 1237, 626), radius=12, fill=COLORS["panel"], outline=COLORS["border"])
    draw.line((25, 164, 429, 164), fill=COLORS["border"])
    draw.line((447, 164, 1236, 164), fill=COLORS["border"])
    draw.line((42, 575, 412, 575), fill=COLORS["border"])
    draw.text((42, 139), "TERMINAL  /  SYNTHETIC DATA", font=small, fill=COLORS["muted"])
    draw.text((465, 139), "CHART VIEW", font=small, fill=COLORS["muted"])
    draw.text((1218, 139), "OHLCV  /  UTC", font=small, fill=COLORS["muted"], anchor="ra")
    draw.text((25, 637), f"FUZZY TECHNOLOGIES  /  PRICEGENERATOR v{version('pricegenerator')}", font=small, fill=COLORS["muted"])
    draw.text((1237, 637), "SEED 42   •   120 HOURLY BARS", font=small, fill=COLORS["lavender"], anchor="ra")

    return base, (mono, small, heading)


def Record(output):
    """Write a compact looping GIF using a stable palette and readable holds."""

    with tempfile.TemporaryDirectory(prefix="pricegenerator-demo-") as workspace:
        chart, blank, digest = Capture(Path(workspace))

    base, fonts = Layout()
    finished = Frame(base, fonts, chart, blank, digest, 4, reveal=CHART_SIZE[0])
    palette = finished.quantize(colors=128, dither=Image.Dither.NONE)
    frames = []
    durations = []

    def Append(duration, phase, typed=None, reveal=None):
        """Encode a frame with the shared palette and its presentation time."""

        frame = Frame(base, fonts, chart, blank, digest, phase, typed, reveal)
        frames.append(frame.quantize(palette=palette, dither=Image.Dither.NONE))
        durations.append(duration)

    Append(650, 0, 0)

    for index, lines in enumerate(COMMANDS):
        length = sum(map(len, lines))
        visible_width = CHART_SIZE[0] if index > 1 else None

        for typed in range(4, length, 4):
            Append(70, index, typed, visible_width)

        Append(460, index, length, visible_width)

        if index == 1:
            for width in range(92, CHART_SIZE[0], 28):
                Append(70, 2, 0, width)

    Append(3100, 4, reveal=CHART_SIZE[0])
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)


def Main():
    """Parse the output path and record the CLI demo."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    Record(arguments.output)


if __name__ == "__main__":
    Main()
