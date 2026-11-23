"""Build the download and illustration for the published 32-path example."""

import argparse
import csv
from io import StringIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import matplotlib
import matplotlib.pyplot as plt


def Build(source, output):
    """Package the original hourly CSV files and draw their 32 closing-price paths."""

    files = [source / f"path-{index:02d}.csv" for index in range(32)]
    matplotlib.rcParams.update({"svg.fonttype": "none", "svg.hashsalt": "pricegenerator-2.2.1"})
    background, grid, text = "#101822", "#354252", "#dce6ef"
    figure, axes = plt.subplots(figsize=(9, 4.8), layout="constrained", facecolor=background)
    axes.set_facecolor(background)

    with ZipFile(output / "monte-carlo-32-paths.zip", "w") as archive:
        for index, path in enumerate(files):
            with path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))

            if len(rows) != 120:
                raise ValueError(f"{path.name} must contain 120 hourly candles")

            entry = ZipInfo(path.name)
            entry.create_system = 3
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, path.read_bytes(), compress_type=ZIP_DEFLATED)
            prices = [float(rows[0]["open"]), *(float(row["close"]) for row in rows)]
            line, = axes.plot(range(len(prices)), prices, color="#8ba1b5", linewidth=1.05, alpha=0.54,
                              gid=f"price-path-{index:02d}")

            if index == 0:
                line.set(color="#51d9da", linewidth=2.2, alpha=1, zorder=4, label="Path 00")

            elif index == 1:
                line.set_label("31 other paths")

    axes.set_title("32 simulated price paths", loc="left", color=text, fontsize=18, pad=13)
    axes.set_xlabel("Hours since the start of the simulation", color=text)
    axes.set_ylabel("Price", color=text)
    axes.set_xticks(range(0, 121, 24))
    axes.set_xlim(0, 120)
    axes.tick_params(colors=text)
    axes.set_axisbelow(True)
    axes.grid(axis="y", color=grid, linewidth=0.6)
    axes.spines[:].set_visible(False)
    axes.legend(loc="upper left", frameon=False, labelcolor=text, ncol=2)
    svg = StringIO()
    figure.savefig(svg, format="svg", metadata={"Date": None})
    plt.close(figure)
    lines = (line.rstrip() for line in svg.getvalue().splitlines())
    (output / "monte-carlo-32-paths.svg").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def Main():
    """Read the exported example paths and write the corresponding Pages assets."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    Build(args.paths, args.output)


if __name__ == "__main__":
    Main()
