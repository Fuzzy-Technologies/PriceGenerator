"""Generate standalone SVG charts without browser or optional dependencies."""

import hashlib
from datetime import datetime
from html import escape
from pathlib import Path
import textwrap
from typing import Callable

from .spec import ChartSpec
from .theme import BrandingData, THEMES


def _Coordinate(value: float) -> str:
    """Keep geometry compact and stable across repeated exports."""

    return f"{value:.3f}".rstrip("0").rstrip(".")


def _PriceLabel(value: float, precision: int) -> str:
    """Keep axis labels bounded for very large or very small prices."""

    if abs(value) >= 1e9 or (value != 0 and abs(value) < 10 ** -precision):
        return f"{value:.3e}"

    return f"{value:.{precision}f}"


def _Scale(spec: ChartSpec, top: float, bottom: float) -> tuple[Callable[[float], float], list[float]]:
    """Compute a finite price transform including every visible overlay."""

    values = [value for candle in spec.candles for value in (candle.low, candle.high)]

    for series in spec.series:
        if series.visible:
            values.extend(value for value in series.values if value is not None)

    minimum, maximum = min(values), max(values)
    magnitude = max(abs(minimum), abs(maximum), 1.0)
    low, high = minimum / magnitude, maximum / magnitude
    padding = (high - low) * 0.08 if high > low else max(abs(high) * 0.02, 1e-6)
    low -= padding
    high += padding

    def Position(value: float) -> float:
        """Map a finite value without overflowing extreme-price differences."""

        return bottom - ((value / magnitude - low) / (high - low)) * (bottom - top)

    # Ticks stay inside the observed domain to avoid overflow when multiplying.
    ticks = [minimum * (1 - step / 4) + maximum * (step / 4) for step in range(5)]

    return Position, ticks


def _WrappedLines(lines: tuple[str, ...], width: int) -> list[str]:
    """Wrap plain text for the exported report instead of cropping it."""

    result = []

    for line in lines:
        for paragraph in line.split("\n"):
            result.extend(textwrap.wrap(paragraph, width=width, replace_whitespace=False) or [""])

    return result


def RenderSVG(spec: ChartSpec) -> str:
    """Render candles, volume, visible overlays, markers, and a report as SVG."""

    if not isinstance(spec, ChartSpec):
        raise ValueError("spec must be a validated ChartSpec")

    theme = THEMES[spec.theme]
    branding = BrandingData()
    prefix = "pg-" + hashlib.sha256(spec.ToJSON().encode("utf-8")).hexdigest()[:12]
    title_lines = _WrappedLines((spec.title,), max(20, (spec.width - 140) // 12))
    title_height = max(88, 56 + len(title_lines) * 22)
    chart_height = spec.height + max(0, title_height - 88)
    price_top, price_bottom = float(title_height), float(chart_height - 146)
    volume_top, volume_bottom = price_bottom + 25, float(chart_height - 52)
    position_y, ticks = _Scale(spec, price_top, price_bottom)
    label_width = max(len(_PriceLabel(tick, spec.price_precision)) for tick in ticks) * 7
    left, right = float(max(92, label_width + 20)), float(spec.width - 28)
    count = len(spec.candles)
    instants = [datetime.fromisoformat(candle.datetime.replace("Z", "+00:00")) for candle in spec.candles]
    deltas = [instant - instants[0] for instant in instants]
    timestamps = [delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000 for delta in deltas]
    interval = min((b - a for a, b in zip(timestamps, timestamps[1:])), default=1000)
    time_span = timestamps[-1] - timestamps[0] + interval
    positions_x = [left + (right - left) * (timestamp - timestamps[0] + interval / 2) / time_span for timestamp in timestamps]
    body_width = max(0.75, min(16.0, (right - left) * interval / time_span * 0.65))
    palette = [theme[key] for key in ("accent", "secondary", "warning", "up", "down")]
    legend_entries = []

    for index, series in enumerate(spec.series):
        if series.visible:
            color = series.color or palette[index % len(palette)]
            legend_entries.extend((line, color, series.kind, series.dashed) for line in _WrappedLines((series.label,), max(20, (spec.width - 100) // 8)))

    report_lines = _WrappedLines(spec.summary, max(20, (spec.width - 60) // 8))
    extra_height = (len(legend_entries) + len(report_lines)) * 19 + (44 if legend_entries or report_lines else 0)
    total_height = chart_height + extra_height
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{spec.width}" height="{total_height}" viewBox="0 0 {spec.width} {total_height}" role="img" aria-labelledby="{prefix}-title {prefix}-description">',
        f'<title id="{prefix}-title">{escape(spec.title)}</title>',
        f'<desc id="{prefix}-description">OHLCV chart of {count} candles in UTC. Rising candles have a hollow body; falling candles have a filled body. Volume uses the same direction colors. Static exports show only visible overlays. Fuzzy Technologies.</desc>',
        f'<defs><clipPath id="{prefix}-plot"><rect x="{left}" y="{price_top}" width="{right - left}" height="{price_bottom - price_top}"/></clipPath>',
        f'<clipPath id="{prefix}-volume"><rect x="{left}" y="{volume_top}" width="{right - left}" height="{volume_bottom - volume_top}"/></clipPath>',
        f'<clipPath id="{prefix}-emblem-clip"><circle cx="28" cy="28" r="28"/></clipPath>',
        f'<filter id="{prefix}-wordmark-tint"><feFlood flood-color="{theme["text"]}"/><feComposite in2="SourceAlpha" operator="in"/></filter>',
        f'<image id="{prefix}-wordmark" xlink:href="{branding["wordmark"]}" width="160" height="28.8"/>',
        f'<image id="{prefix}-emblem" xlink:href="{branding["emblem"]}" width="56" height="56" clip-path="url(#{prefix}-emblem-clip)"/></defs>',
        f'<rect width="100%" height="100%" fill="{theme["background"]}"/>',
        f'<g font-family="DejaVu Sans Mono,Consolas,monospace" fill="{theme["text"]}">',
        f'<use href="#{prefix}-emblem" xlink:href="#{prefix}-emblem" x="{spec.width - 84}" y="14"/>',
    ]

    for index, line in enumerate(title_lines):
        pieces.append(f'<text x="28" y="{35 + index * 22}" font-size="19" font-weight="600">{escape(line)}</text>')

    pieces.append(f'<text x="28" y="{title_height - 20}" font-size="11" fill="{theme["muted"]}">PRICEGENERATOR / FUZZY TECHNOLOGIES / UTC</text>')
    pieces.append(f'<rect x="{left}" y="{price_top}" width="{right - left}" height="{volume_bottom - price_top}" fill="{theme["panel"]}"/>')

    for tick in dict.fromkeys(ticks):
        y = _Coordinate(position_y(tick))
        pieces.append(f'<path d="M {left} {y} H {right}" stroke="{theme["grid"]}" stroke-dasharray="3 6"/>')
        pieces.append(f'<text x="{left - 9}" y="{y}" dy="4" font-size="11" text-anchor="end" fill="{theme["muted"]}">{_PriceLabel(tick, spec.price_precision)}</text>')

    maximum_volume = max(candle.volume for candle in spec.candles) or 1.0

    for index, candle in enumerate(spec.candles):
        x = positions_x[index]
        color = theme["up"] if candle.close >= candle.open else theme["down"]
        top, bottom = sorted((position_y(candle.open), position_y(candle.close)))
        body_height = max(1.0, bottom - top)
        fill = theme["panel"] if candle.close >= candle.open else color
        pieces.append(f'<g data-candle-index="{index}" stroke="{color}" stroke-width="1"><title>{escape(candle.datetime)} O={candle.open} H={candle.high} L={candle.low} C={candle.close} V={candle.volume}</title>')
        pieces.append(f'<path d="M {_Coordinate(x)} {_Coordinate(position_y(candle.high))} V {_Coordinate(position_y(candle.low))}"/>')
        pieces.append(f'<rect x="{_Coordinate(x - body_width / 2)}" y="{_Coordinate(top)}" width="{_Coordinate(body_width)}" height="{_Coordinate(body_height)}" fill="{fill}"/></g>')
        volume_height = candle.volume / maximum_volume * (volume_bottom - volume_top)
        pieces.append(f'<rect data-volume-index="{index}" x="{_Coordinate(x - body_width / 2)}" y="{_Coordinate(volume_bottom - volume_height)}" width="{_Coordinate(body_width)}" height="{_Coordinate(volume_height)}" fill="{color}" opacity="0.6"/>')

    pieces.append(f'<g clip-path="url(#{prefix}-plot)">')

    for series_index, series in enumerate(spec.series):
        if not series.visible:
            continue

        color = series.color or palette[series_index % len(palette)]
        pieces.append(f'<g data-series="{series.key}" fill="none" stroke="{color}" stroke-width="{series.width}"' + (' stroke-dasharray="5 4"' if series.dashed else '') + '>')
        commands = []
        connected = False

        for index, value in enumerate(series.values):
            if value is None:
                connected = False
                continue

            x, y = _Coordinate(positions_x[index]), _Coordinate(position_y(value))

            if series.kind == "points":
                pieces.append(f'<circle cx="{x}" cy="{y}" r="{series.width + 1}" fill="{color}"/>')

            else:
                commands.append(f'{"L" if connected else "M"} {x} {y}')
                connected = True

        if commands:
            pieces.append('<path d="' + ' '.join(commands) + '"/>')

        pieces.append('</g>')

    pieces.append('</g>')
    pieces.append(f'<g data-watermark-panel="price" clip-path="url(#{prefix}-plot)" opacity="0.28">')
    pieces.append(f'<use href="#{prefix}-wordmark" xlink:href="#{prefix}-wordmark" x="{left + 8}" y="{price_bottom - 36.8}" filter="url(#{prefix}-wordmark-tint)"/></g>')

    for marker in spec.markers:
        candle = spec.candles[marker.candle_index]
        x = positions_x[marker.candle_index]

        if marker.position == "above":
            y = position_y(candle.high) - 8

        elif marker.position == "below":
            y = position_y(candle.low) + 17

        else:
            y = position_y(candle.low / 2 + candle.high / 2) + 4

        available = max(x - 12, spec.width - 12 - x)
        marker_lines = _WrappedLines((marker.text,), max(1, int(available / 8)))

        if len(marker_lines) > 3:
            marker_lines = marker_lines[:3]
            marker_lines[-1] = marker_lines[-1][:-1] + "…"

        text_width = max(map(len, marker_lines)) * 8
        anchor = "middle"

        if x - text_width / 2 < 12 or x + text_width / 2 > spec.width - 12:
            anchor = "start" if x < spec.width / 2 else "end"

        if marker.position == "above":
            y -= (len(marker_lines) - 1) * 15

        elif marker.position == "center":
            y -= (len(marker_lines) - 1) * 7.5

        y = max(price_top + 14, min(y, price_bottom + 19 - (len(marker_lines) - 1) * 15))
        pieces.append(f'<text data-marker="{marker.candle_index}" x="{_Coordinate(x)}" y="{_Coordinate(y)}" text-anchor="{anchor}" font-size="13" fill="{marker.color or theme["accent"]}">')
        pieces.append(f'<title>{escape(marker.text)}</title>')

        for line_index, line in enumerate(marker_lines):
            pieces.append(f'<tspan x="{_Coordinate(x)}" dy="{0 if line_index == 0 else 15}">{escape(line)}</tspan>')

        pieces.append('</text>')

    tick_indices = {0, count - 1}

    if right - left >= 500:
        tick_indices.add(count // 2)

    for index in sorted(tick_indices):
        x = positions_x[index]
        date_length = 23 if interval < 1000 else 19 if interval < 60_000 else 16
        label = spec.candles[index].datetime[:date_length].replace("T", " ")
        anchor = "middle" if count == 1 else "start" if index == 0 else "end" if index == count - 1 else "middle"
        pieces.append(f'<text x="{_Coordinate(x)}" y="{volume_bottom + 22}" font-size="10" text-anchor="{anchor}" fill="{theme["muted"]}">{label}</text>')

    pieces.append(f'<text x="{left - 9}" y="{volume_top + 12}" text-anchor="end" font-size="11" fill="{theme["muted"]}">Volume</text>')

    for index, (line, color, kind, dashed) in enumerate(legend_entries):
        y = chart_height + 16 + index * 19

        if kind == "points":
            pieces.append(f'<circle cx="41" cy="{y - 4}" r="2.5" fill="{color}"/>')

        else:
            pieces.append(f'<path d="M 28 {y - 4} H 54" stroke="{color}" stroke-width="2"' + (' stroke-dasharray="5 4"' if dashed else '') + '/>')

        pieces.append(f'<text x="64" y="{y}" font-size="12" fill="{theme["muted"]}">{escape(line)}</text>')

    for index, line in enumerate(report_lines):
        y = chart_height + 28 + (len(legend_entries) + index) * 19
        pieces.append(f'<text x="28" y="{y}" font-size="12" fill="{theme["muted"]}">{escape(line)}</text>')

    pieces.append('</g></svg>')

    return '\n'.join(pieces)


def SaveSVG(spec: ChartSpec, path: str | Path) -> Path:
    """Write a complete offline SVG and return its path, propagating I/O errors."""

    destination = Path(path)
    rendered = RenderSVG(spec)
    destination.write_text(rendered, encoding="utf-8")

    return destination
