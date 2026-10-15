"""Bridge existing price data to charts without mutating caller-owned state."""

from copy import copy, deepcopy
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


def _UnshiftedHMA(close):
    """Offer the documented HMA5 correction using the actual installed TA backend."""

    try:
        backend = import_module("pandas_ta_classic")

    except ModuleNotFoundError as error:
        if error.name != "pandas_ta_classic":
            raise

        try:
            backend = import_module("pandas_ta")

        except ModuleNotFoundError as legacy_error:
            if legacy_error.name != "pandas_ta":
                raise

            raise ImportError('HMA analysis requires: python -m pip install "pricegenerator[indicators]"') from legacy_error

    return backend.hma(close=close, length=5, offset=None)


def _LegacySeries(model, candles: tuple[ChartCandle, ...], hma5_mode: str) -> tuple[ChartSeries, ...]:
    """Retain the actual historical indicator formulas and overlay visibility."""

    length = len(candles)
    statistics = model.stat
    maximum = round(float(statistics["closeMax"]), model.precision)
    minimum = round(float(statistics["closeMin"]), model.precision)
    result = [
        ChartSeries("close-max", f"Max close: {maximum}", (maximum,) * length, group="Close limits and trends"),
        ChartSeries("close-min", f"Min close: {minimum}", (minimum,) * length, group="Close limits and trends"),
        ChartSeries("trend", "Full-horizon trend", _Interpolate(candles, [0, length - 1], [candles[0].close, candles[-1].close]), group="Close limits and trends", dashed=True),
        ChartSeries("average-line", "High/low midpoint", _Values(model.prices.avg, length), visible=False, group="Midpoint"),
        ChartSeries("average-points", "High/low midpoint points", _Values(model.prices.avg, length), kind="points", visible=False, group="Midpoint"),
    ]

    if model.trendSplit and model.splitCount:
        if any(type(count) is not int or count < 1 for count in model.splitCount) or sum(model.splitCount) != length:
            raise ValueError("legacy splitCount must contain positive counts summing to the candle count")

        left = 0

        for index, count in enumerate(model.splitCount):
            right = left + count - 1
            positions = [left] if left == right else [left, right]
            values = [candles[position].close for position in positions]
            result.append(ChartSeries(f"trend-segment-{index + 1}", f"Segment {index + 1} trend", _Interpolate(candles, positions, values), group="Close limits and trends", dashed=True))
            left += count

    definitions = (
        ("sma5", "SMA 5", "SMA 5 / 20"), ("sma20", "SMA 20", "SMA 5 / 20"),
        ("sma50", "SMA 50", "SMA 50 / 200"), ("sma200", "SMA 200", "SMA 50 / 200"),
        ("hma5", "HMA 5 (legacy shift 3)" if hma5_mode == "legacy" else "HMA 5 (unshifted)", "HMA 5 / 20"),
        ("hma20", "HMA 20", "HMA 5 / 20"),
        ("vwma5", "VWMA 5", "VWMA 5 / 20"), ("vwma20", "VWMA 20", "VWMA 5 / 20"),
    )

    for key, label, group in definitions:
        values = _UnshiftedHMA(model.prices.close) if key == "hma5" and hma5_mode == "unshifted" else statistics[key]
        result.append(ChartSeries(key, label, _Values(values, length), visible=False, group=group))

    for key in ("lower", "mid", "upper"):
        result.append(ChartSeries(f"bbands-{key}", f"Bollinger {key}", _Values(statistics["bbands"][key], length), visible=False, group="Bollinger bands"))

    for key in ("long", "short"):
        result.append(ChartSeries(f"psar-{key}", f"PSAR {key}", _Values(statistics["psar"][key], length), kind="points", visible=False, group="PSAR"))

    for key, label in (("hma13", "Jaw: HMA 13, shift 8"), ("hma8", "Teeth: HMA 8, shift 5"), ("hma5", "Lips: HMA 5, shift 3")):
        result.append(ChartSeries(f"alligator-{key}", label, _Values(statistics[key], length), visible=False, group="Alligator (historical HMA formulas)"))

    zigzag = statistics["zigzag3"]
    positions = list(zigzag.index)
    values = list(zigzag["filtered"])
    result.append(ChartSeries("zigzag", f"Zig-Zag ({model.zigZagDeviation * 100:g}%)", _Interpolate(candles, positions, values), visible=False, group="Zig-Zag"))

    return tuple(result)


def BuildLegacyChart(
    model, *, include_statistics: bool = True, assume_timezone: str | None = None,
    markers=None, lines=(), title: str | None = None, theme: str = "dark", width: int = 1280,
    height: int = 760, show_controls: bool = True, hma5_mode: str = "legacy",
) -> ChartSpec:
    """Adapt an existing PriceGenerator with optional analysis on a detached copy."""

    if not isinstance(include_statistics, bool) or hma5_mode not in {"legacy", "unshifted"}:
        raise ValueError("include_statistics must be boolean and hma5_mode must be 'legacy' or 'unshifted'")

    snapshot = _FrameSnapshot(model.prices, _PRICE_COLUMNS, "model.prices")
    base = FromDataFrame(
        snapshot, assume_timezone=assume_timezone, title=title or getattr(model, "_chartTitle", "") or f"Instrument: {model.ticker}",
        markers=markers, lines=lines, theme=theme, width=width, height=height,
        price_precision=model.precision, show_controls=show_controls,
    )

    if not include_statistics:
        return base

    if len(snapshot) < 5 or any(candle.close == 0 for candle in base.candles):
        raise ValueError("Legacy analysis requires at least five candles and nonzero closes; use include_statistics=False for raw charts")

    detached = copy(model)
    detached.prices = snapshot
    detached._stat = deepcopy(model.stat)
    detached.horizon = len(snapshot)
    detached.prices["datetime"] = _Pandas().to_datetime([candle.datetime for candle in base.candles], utc=True)
    detached.DetectTimeframe()
    summary = tuple(detached.GetStatistics())

    return ChartSpec(
        candles=base.candles, title=title or detached._chartTitle,
        series=_LegacySeries(detached, base.candles, hma5_mode) + base.series,
        markers=base.markers, summary=summary, theme=theme, width=width, height=height,
        price_precision=detached.precision, show_controls=show_controls,
    )


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
