"""Validate immutable, renderer-independent financial chart descriptions."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from numbers import Real
import re
from typing import Any, Mapping


SCHEMA_VERSION = 1
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
_SERIES_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,79}\Z")


def _Text(value: Any, field: str) -> str:
    """Reject non-text values and XML-invalid control characters."""

    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")

    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise ValueError(f"{field} contains an unsupported control character")

    if any(0xD800 <= ord(char) <= 0xDFFF or ord(char) in (0xFFFE, 0xFFFF) for char in value):
        raise ValueError(f"{field} contains an invalid Unicode character")

    return value


def _Number(value: Any, field: str) -> float:
    """Normalize finite real numbers without accepting booleans."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a finite number")

    try:
        number = float(value)

    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc

    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")

    return number


def _Integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    """Validate bounded integer configuration without coercion."""

    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{field} must be an integer from {minimum} to {maximum}")

    return value


def _Color(value: Any, field: str) -> str | None:
    """Allow a bounded color grammar instead of arbitrary SVG or CSS."""

    if value is not None and (not isinstance(value, str) or not _HEX_COLOR.fullmatch(value)):
        raise ValueError(f"{field} must be a six-digit hexadecimal color or None")

    return value


def _Timestamp(value: Any) -> str:
    """Normalize explicit-offset ISO timestamps at browser-safe precision."""

    if not isinstance(value, str) or "T" not in value:
        raise ValueError("datetime must be an ISO timestamp with an explicit timezone")

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("datetime must include an explicit timezone")

        parsed = parsed.astimezone(timezone.utc)

    except (ValueError, OverflowError) as exc:
        raise ValueError("datetime must be a valid ISO timestamp with an explicit timezone") from exc

    if parsed.microsecond % 1000:
        raise ValueError("datetime precision must not exceed milliseconds")

    return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class ChartCandle:
    """One validated OHLCV candle with an explicit UTC timestamp."""

    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        """Normalize primitives and enforce the canonical OHLCV invariants."""

        object.__setattr__(self, "datetime", _Timestamp(self.datetime))

        for field in ("open", "high", "low", "close", "volume"):
            object.__setattr__(self, field, _Number(getattr(self, field), field))

        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("candle must satisfy low <= min(open, close) <= max(open, close) <= high")

        if self.volume < 0:
            raise ValueError("volume must be non-negative")


@dataclass(frozen=True)
class ChartSeries:
    """An aligned line or point overlay, with explicit gaps and visibility."""

    key: str
    label: str
    values: tuple[float | None, ...]
    color: str | None = None
    kind: str = "line"
    visible: bool = True
    group: str | None = None
    width: float = 1.8
    dashed: bool = False

    def __post_init__(self) -> None:
        """Snapshot overlay values and reject unsupported rendering options."""

        if not isinstance(self.key, str) or not _SERIES_KEY.fullmatch(self.key):
            raise ValueError("series key must start with a letter and contain at most 80 identifier characters")

        _Text(self.label, "series label")
        _Color(self.color, "series color")

        if self.group is not None:
            _Text(self.group, "series group")

        if self.kind not in ("line", "points"):
            raise ValueError("series kind must be 'line' or 'points'")

        if not isinstance(self.visible, bool) or not isinstance(self.dashed, bool):
            raise ValueError("series visible and dashed must be booleans")

        width = _Number(self.width, "series width")

        if not 0 < width <= 20:
            raise ValueError("series width must be greater than zero and at most 20")

        if isinstance(self.values, (str, bytes, Mapping)):
            raise ValueError("series values must be a sequence of numbers or None")

        try:
            values = tuple(None if value is None else _Number(value, "series value") for value in self.values)

        except TypeError as exc:
            raise ValueError("series values must be a sequence") from exc

        object.__setattr__(self, "values", values)
        object.__setattr__(self, "width", width)


@dataclass(frozen=True)
class ChartMarker:
    """Plain-text annotation positioned relative to one candle."""

    candle_index: int
    text: str
    position: str = "above"
    color: str | None = None

    def __post_init__(self) -> None:
        """Validate marker semantics before either renderer sees them."""

        _Integer(self.candle_index, "marker candle_index", 0, 2**31 - 1)
        _Text(self.text, "marker text")
        _Color(self.color, "marker color")

        if self.position not in ("above", "center", "below"):
            raise ValueError("marker position must be 'above', 'center', or 'below'")


@dataclass(frozen=True)
class ChartSpec:
    """A complete chart snapshot independent of pandas and browser libraries."""

    candles: tuple[ChartCandle, ...]
    title: str = "PriceGenerator"
    series: tuple[ChartSeries, ...] = ()
    markers: tuple[ChartMarker, ...] = ()
    summary: tuple[str, ...] = ()
    theme: str = "dark"
    width: int = 1280
    height: int = 760
    price_precision: int = 2
    show_controls: bool = True

    def __post_init__(self) -> None:
        """Validate chart-wide ordering, alignments, and finite configuration."""

        _Text(self.title, "title")
        _Integer(self.width, "width", 480, 16384)
        _Integer(self.height, "height", 360, 16384)
        _Integer(self.price_precision, "price_precision", 0, 12)

        if self.theme not in ("dark", "light"):
            raise ValueError("theme must be 'dark' or 'light'")

        if not isinstance(self.show_controls, bool):
            raise ValueError("show_controls must be a boolean")

        for field in ("candles", "series", "markers", "summary"):
            if isinstance(getattr(self, field), (str, bytes, Mapping)):
                raise ValueError(f"{field} must be a sequence")

            try:
                object.__setattr__(self, field, tuple(getattr(self, field)))

            except TypeError as exc:
                raise ValueError(f"{field} must be a sequence") from exc

        if not self.candles or any(not isinstance(candle, ChartCandle) for candle in self.candles):
            raise ValueError("candles must contain at least one ChartCandle")

        times = [candle.datetime for candle in self.candles]

        if any(left >= right for left, right in zip(times, times[1:])):
            raise ValueError("candle timestamps must be strictly increasing and unique")

        keys = set()

        for series in self.series:
            if not isinstance(series, ChartSeries) or len(series.values) != len(self.candles):
                raise ValueError("each ChartSeries must contain one value or None per candle")

            if series.key in keys:
                raise ValueError("series keys must be unique")

            keys.add(series.key)

        for marker in self.markers:
            if not isinstance(marker, ChartMarker) or marker.candle_index >= len(self.candles):
                raise ValueError("each ChartMarker must reference an existing candle")

        for line in self.summary:
            _Text(line, "summary line")

    def ToDict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible representation with a version."""

        data = asdict(self)
        data["schema_version"] = SCHEMA_VERSION

        return data

    def ToJSON(self) -> str:
        """Serialize deterministically without allowing an HTML script escape."""

        serialized = json.dumps(self.ToDict(), ensure_ascii=False, allow_nan=False, separators=(",", ":"))

        return serialized.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    @classmethod
    def FromDict(cls, data: Mapping[str, Any]) -> "ChartSpec":
        """Restore a validated snapshot without accepting unknown schema fields."""

        if not isinstance(data, Mapping):
            raise ValueError("chart specification must be an object")

        values = dict(data)

        if type(values.pop("schema_version", None)) is not int or data["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")

        try:
            for field, item_type in (("candles", ChartCandle), ("series", ChartSeries), ("markers", ChartMarker)):
                values[field] = tuple(item_type(**item) for item in values.get(field, ()))

            return cls(**values)

        except (TypeError, KeyError) as exc:
            raise ValueError("chart specification contains invalid or unknown fields") from exc
