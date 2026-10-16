"""Bridge existing price data to charts without mutating caller-owned state."""

from datetime import datetime
from html import escape
from importlib import import_module
from pathlib import Path
from typing import Any

from .spec import ChartCandle, ChartMarker, ChartSeries, ChartSpec


_PRICE_COLUMNS = ("datetime", "open", "high", "low", "close", "volume")
_MARKER_COLUMNS = {"markersUpper": "above", "markersCenter": "center", "markersLower": "below"}


def _Pandas():
    """Load the DataFrame integration only when it is explicitly requested."""

    try:
        return import_module("pandas")

    except ModuleNotFoundError as error:
        if error.name != "pandas":
            raise

        raise ImportError("DataFrame chart adapters require pandas; plain ChartSpec rendering does not.") from error


def _FrameSnapshot(frame, required_columns: tuple[str, ...], field: str):
    """Require a nonempty DataFrame with unambiguous columns and detach its rows."""

    pandas = _Pandas()

    if not isinstance(frame, pandas.DataFrame) or frame.empty:
        raise ValueError(f"{field} must be a nonempty pandas DataFrame")

    if not frame.columns.is_unique or any(column not in frame.columns for column in required_columns):
        raise ValueError(f"{field} requires unique columns including {', '.join(required_columns)}")

    return frame.copy(deep=True).reset_index(drop=True)


def _Timestamp(value, assume_timezone: str | None, pandas) -> str:
    """Preserve aware times and reject ambiguous naive or submillisecond input."""

    if not isinstance(value, (str, datetime, pandas.Timestamp)):
        raise ValueError("datetime must be a timestamp or ISO text, not an implicit epoch number")

    if assume_timezone is not None and (not isinstance(assume_timezone, str) or not assume_timezone):
        raise ValueError("assume_timezone must be a nonempty timezone name or None")

    try:
        timestamp = pandas.Timestamp(value)

        if pandas.isna(timestamp):
            raise ValueError("datetime cannot be missing")

        if timestamp.tzinfo is None:
            if assume_timezone is None:
                raise ValueError("naive datetime requires an explicit assume_timezone")

            timestamp = timestamp.tz_localize(assume_timezone, ambiguous="raise", nonexistent="raise")

        if timestamp.nanosecond or timestamp.microsecond % 1000:
            raise ValueError("datetime precision must not exceed milliseconds")

        return timestamp.tz_convert("UTC").isoformat(timespec="milliseconds")

    except (TypeError, OverflowError) as error:
        raise ValueError("datetime must be a valid timestamp with an explicit timezone") from error


def _Values(values, length: int) -> tuple[float | None, ...]:
    """Convert indicator warmup gaps to None without silently accepting infinities."""

    if values is None:
        return (None,) * length

    pandas = _Pandas()
    result = tuple(None if value is None or pandas.isna(value) else value for value in values)

    if len(result) != length:
        raise ValueError("analysis overlay must have exactly one value per candle")

    return result


def _AlignedFrame(frame, candles: tuple[ChartCandle, ...], assume_timezone: str | None, field: str, reference_times, pandas):
    """Map sparse annotations by exact timestamps instead of positional guessing."""

    frame = _FrameSnapshot(frame, ("datetime",), field)

    # Typed datetime equality preserves the validated scalar type. Object equality
    # can equate unsupported numpy.datetime64 with supported Python datetime values.
    if pandas.api.types.is_datetime64_any_dtype(reference_times.dtype) and frame["datetime"].equals(reference_times):
        return frame, range(len(candles))

    lookup = {candle.datetime: index for index, candle in enumerate(candles)}
    indices = []

    for value in frame["datetime"]:
        normalized = _Timestamp(value, assume_timezone, pandas).replace("+00:00", "Z")

        if normalized not in lookup:
            raise ValueError(f"{field} contains a timestamp absent from the candle data")

        indices.append(lookup[normalized])

    if len(set(indices)) != len(indices):
        raise ValueError(f"{field} must not contain duplicate candle timestamps")

    return frame, indices


def _CustomMarkers(markers, candles: tuple[ChartCandle, ...], assume_timezone: str | None, reference_times, pandas) -> tuple[ChartMarker, ...]:
    """Translate the three historical text-marker columns without changing prices."""

    if markers is None:
        return ()

    frame, indices = _AlignedFrame(markers, candles, assume_timezone, "markers", reference_times, pandas)
    columns = [column for column in _MARKER_COLUMNS if column in frame.columns]

    if not columns:
        raise ValueError("markers require markersUpper, markersCenter or markersLower")

    result = []

    for column in columns:
        for index, text in zip(indices, frame[column]):
            if text is None or pandas.isna(text) or text == "":
                continue

            if not isinstance(text, str):
                raise ValueError("custom marker text must be a string or missing")

            result.append(ChartMarker(index, text, position=_MARKER_COLUMNS[column]))

    return tuple(result)


def _CustomLines(lines, candles: tuple[ChartCandle, ...], assume_timezone: str | None, reference_times, pandas) -> tuple[ChartSeries, ...]:
    """Align named custom columns with explicit gaps and no implicit interpolation."""

    if lines is None:
        return ()

    if not isinstance(lines, (tuple, list)):
        raise ValueError("lines must be a sequence of pandas DataFrames")

    overlays = []

    for frame_index, line in enumerate(lines):
        frame, indices = _AlignedFrame(line, candles, assume_timezone, "custom line", reference_times, pandas)
        columns = [column for column in frame.columns if column != "datetime"]

        if not columns or any(not isinstance(column, str) or not column for column in columns):
            raise ValueError("custom lines require at least one named value column")

        for column_index, column in enumerate(columns):
            values = [None] * len(candles)

            for index, value in zip(indices, _Values(frame[column], len(frame))):
                values[index] = value

            overlays.append(ChartSeries(
                key=f"custom-{frame_index}-{column_index}", label=column, values=values,
                group=f"Custom: {column}", width=2,
            ))

    return tuple(overlays)


def FromDataFrame(
    prices, *, assume_timezone: str | None = None, title: str = "PriceGenerator",
    markers=None, lines=(), series=(), summary=(), theme: str = "dark", width: int = 1280,
    height: int = 760, price_precision: int = 2, show_controls: bool = True,
) -> ChartSpec:
    """Snapshot OHLCV data and caller-supplied overlays without running analysis."""

    frame = _FrameSnapshot(prices, _PRICE_COLUMNS, "prices")
    pandas = _Pandas()
    reference_times = frame["datetime"]
    candles = tuple(
        ChartCandle(_Timestamp(row[0], assume_timezone, pandas), *row[1:])
        for row in frame[list(_PRICE_COLUMNS)].itertuples(index=False, name=None)
    )

    return ChartSpec(
        candles=candles, title=title, series=tuple(series) + _CustomLines(lines, candles, assume_timezone, reference_times, pandas),
        markers=_CustomMarkers(markers, candles, assume_timezone, reference_times, pandas), summary=summary, theme=theme,
        width=width, height=height, price_precision=price_precision, show_controls=show_controls,
    )


def _Interpolate(candles: tuple[ChartCandle, ...], positions: list[int], values: list[float]) -> tuple[float | None, ...]:
    """Connect only supplied endpoints using elapsed UTC time, without extrapolation."""

    result = [None] * len(candles)

    if not positions:
        return tuple(result)

    times = [datetime.fromisoformat(candle.datetime.replace("Z", "+00:00")) for candle in candles]
    result[positions[0]] = values[0]

    for left, right, first, last in zip(positions, positions[1:], values, values[1:]):
        duration = (times[right] - times[left]).total_seconds()

        for index in range(left, right + 1):
            ratio = (times[index] - times[left]).total_seconds() / duration
            result[index] = (1 - ratio) * first + ratio * last

    return tuple(result)


def IndicatorOverlays(report) -> tuple[ChartSeries, ...]:
    """Convert modern detached indicator values to explicitly hidden chart overlays."""

    return tuple(ChartSeries(item.key, item.label, item.values, group=item.group, kind=item.kind, visible=False) for item in report.series)


def MarketOverlays(frame, *, split_counts=(), zigzag_deviation: float = 0.05) -> tuple[ChartSeries, ...]:
    """Explicitly calculate modern indicators, price limits, midpoint and time trends."""

    from ..indicators import Indicators
    from ..market_data import ValidateOHLCV

    prices = ValidateOHLCV(frame)
    candles = FromDataFrame(prices).candles
    length = len(candles)
    closing = tuple(float(value) for value in prices.close)
    midpoint = tuple(float(high / 2 + low / 2) for high, low in zip(prices.high, prices.low))
    result = [
        ChartSeries("close-max", "Maximum close", (max(closing),) * length, group="Close limits and trends"),
        ChartSeries("close-min", "Minimum close", (min(closing),) * length, group="Close limits and trends"),
        ChartSeries("trend", "Full-horizon endpoint trend", _Interpolate(candles, [0] if length == 1 else [0, length - 1], [closing[0]] if length == 1 else [closing[0], closing[-1]]), group="Close limits and trends", dashed=True),
        ChartSeries("midpoint-line", "High/low midpoint", midpoint, visible=False, group="Midpoint"),
        ChartSeries("midpoint-points", "High/low midpoint points", midpoint, kind="points", visible=False, group="Midpoint"),
    ]

    if split_counts:
        if any(type(count) is not int or count < 1 for count in split_counts) or sum(split_counts) != length:
            raise ValueError("split_counts must be positive integers summing to the candle count")

        left = 0

        for index, count in enumerate(split_counts):
            right = left + count - 1
            positions = [left] if left == right else [left, right]
            result.append(ChartSeries(f"trend-segment-{index + 1}", f"Segment {index + 1} endpoint trend", _Interpolate(candles, positions, [closing[position] for position in positions]), group="Close limits and trends", dashed=True))
            left += count

    indicators = Indicators(prices, zigzag_deviation=zigzag_deviation)

    for overlay in IndicatorOverlays(indicators):
        if overlay.key == "zigzag":
            positions = [index for index, value in enumerate(overlay.values) if value is not None]
            values = [overlay.values[index] for index in positions]
            overlay = ChartSeries(overlay.key, overlay.label, _Interpolate(candles, positions, values), visible=False, group=overlay.group)

        result.append(overlay)

    return tuple(result)


def RenderMarkdown(spec: ChartSpec) -> str:
    """Return the supplied report as Markdown with raw HTML safely escaped."""

    if not isinstance(spec, ChartSpec):
        raise TypeError("spec must be a validated ChartSpec")

    return f"# {escape(spec.title)}\n\n" + "\n".join(escape(line) for line in spec.summary) + "\n"


def SaveMarkdown(spec: ChartSpec, path: str | Path) -> Path:
    """Write a report only to the explicit path and propagate I/O failures."""

    output_path = Path(path)
    output_path.write_text(RenderMarkdown(spec), encoding="utf-8")

    return output_path


def NotebookHTML(spec: ChartSpec) -> str:
    """Isolate each offline interactive chart in a notebook-safe iframe document."""

    from .interactive import RenderInteractive

    content = escape(RenderInteractive(spec), quote=True)

    return (
        f'<iframe title="{escape(spec.title, quote=True)}" srcdoc="{content}" '
        f'width="100%" height="{spec.height + 280}" loading="lazy" '
        'sandbox="allow-scripts allow-downloads" style="border:0;border-radius:12px"></iframe>'
    )


def DisplayChart(spec: ChartSpec, *, format: str = "html") -> Any:
    """Explicitly display HTML or SVG through the optional notebook integration."""

    if format not in {"html", "svg"}:
        raise ValueError("notebook format must be 'html' or 'svg'")

    try:
        display_module = import_module("IPython.display")

    except ModuleNotFoundError as error:
        if error.name not in {"IPython", "IPython.display"}:
            raise

        raise ImportError('Notebook display requires: python -m pip install "pricegenerator[notebook]"') from error

    if format == "html":
        document = display_module.HTML(NotebookHTML(spec))

    else:
        from .static import RenderSVG

        document = display_module.SVG(RenderSVG(spec))

    return display_module.display(document, display_id=True)
