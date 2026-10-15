# -*- coding: utf-8 -*-
# Author: Timur Gilmullin

"""
**PriceGenerator** is the platform for generating prices similar to real stock prices, but you can control the statistics of their distribution. Generates chain of candlesticks with predefined statistical parameters, return Pandas DataFrame or saving as .CSV-file with OHLCV-candlestick in every string. Use PriceGenerator to generate synthetic data to test your trading strategy.

In additional you can view some statistical and probability parameters of generated or loaded prices.

Sample example:

<a href="https://github.com/Tim55667757/PriceGenerator"><img src="https://github.com/Tim55667757/PriceGenerator/blob/master/media/index_google.html.png?raw=true" alt="Chart" width="780" target="_blank" /></a>

[![gift](https://badgen.net/badge/gift/donate/green)](https://yoomoney.ru/fundraise/BxB9DQNvJnk.230111)
"""

# Copyright (c) 2022 Gilmillin Timur Mansurovich
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import sys
import webbrowser
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union
from datetime import datetime, timedelta

import numpy as np
from dateutil.tz import tzlocal
from argparse import ArgumentParser

from math import pi
from statistics import mode, pstdev, StatisticsError
from itertools import groupby
import pandas as pd
import random

import pricegenerator.UniLogger as uLog
import traceback as tb


if TYPE_CHECKING:
    from bokeh.models import LayoutDOM


def _LoadOptionalDependency(module_name: str, extra: str, feature: str):
    """Load a requested integration without concealing broken installations."""

    try:
        return import_module(module_name)

    except ModuleNotFoundError as error:
        if error.name != module_name:
            raise

        raise ImportError(
            f"{feature} requires optional dependencies. "
            f'Install them with: python -m pip install "pricegenerator[{extra}]"'
        ) from error


# --- Common technical parameters:

uLogger = uLog.UniLogger
uLogger.level = 10  # debug level by default
uLogger.handlers[0].level = 20  # info level by default for STDOUT
# uLogger.handlers[1].level = 10  # debug level by default for log.txt

# Simple internal jinja2 template for rendering static html-page with Google Candlestick chart. `GOOGLE_TEMPLATE_J2` may use with `j2template` variable.
GOOGLE_TEMPLATE_J2 = """{# This template based on Jinja markup language: https://jinja.palletsprojects.com/en/latest/ #}
<!DOCTYPE html>
<html>

<head>
    <title>{{ title }}</title>
    <meta charset="utf-8">
    <script type="text/javascript" src="https://code.jquery.com/jquery-latest.min.js"></script>
    <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
    <script type="text/javascript">google.charts.load('current', {'packages': ['corechart']});</script>
    <style type="text/css">
    #preloader {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: #FFFFFF;
        z-index: 99;
    }
    #status {
        width: 300px;
        height: 150px;
        position: absolute;
        left: 50%;
        top: 50%;
        background-image: url(https://raw.githubusercontent.com/niklausgerber/PreLoadMe/master/img/status.gif);
        background-repeat: no-repeat;
        background-position: left;
        margin: -100px 0 0 -100px;
        font-family: "Segoe UI", "Frutiger", "Frutiger Linotype", "Dejavu Sans", "Helvetica Neue", "Arial", sans-serif;
        font-size: 14px;
    }
    pre {
        font-family: "Lucida Console", sans-serif;
        font-size: 11px;
        padding: 0;
        border-width: 0 0 0 0;
    }
    table {
        font-family: "Segoe UI", "Frutiger", "Frutiger Linotype", "Dejavu Sans", "Helvetica Neue", "Arial", sans-serif;
        font-size: 12px;
        border-spacing: 0;
        text-align: left;
        background: white;
        width: 100%;
    }
    th {
        border-radius: 10px 10px 10px 10px;
        border-style: solid;
        border-width: 0 1px 1px 0;
        border-color: white;
        padding: 6px;
        vertical-align: middle;
        padding-left: 1em;
        background: #E6E6E6;
        height: 50px;
    }
    td {
        border-radius: 10px 10px 10px 10px;
        border-style: solid;
        border-width: 0 1px 1px 0;
        border-color: white;
        padding: 6px;
        vertical-align: top;
        padding-left: 1em;
        background: white;
    }
    </style>
    <script>
    function drawChartCandlesticks(candlesData) {
        var chartOptions = {
            legend: "none",
            titlePosition: "in",
            chartArea: {width: "100%", height: "100%"},
            fontSize: 11,
            candlestick: {
                fallingColor: {stroke: "#000000", strokeWidth: 1, fill: "#999999"},
                risingColor: {stroke: "#000000",  strokeWidth: 1, fill: "#FFFFFF"},
            },
            colors: ["#000000"],
            hAxis: {textPosition: "none"},
            vAxis: {textPosition: "in", textStyle: {fontSize: 12}},
        }
        if (typeof candlesData !== "undefined") {
            var data = google.visualization.arrayToDataTable(candlesData, true);
            var chart = new google.visualization.CandlestickChart(document.getElementById("candlestickChart"));
            chart.draw(data, chartOptions);
        }
    }
    </script>
</head>


<body onload="drawChartCandlesticks({{ candlesData }})">


<!-- Preloader -->
<script>
    $(window).on('load', function() {
        $('#status').fadeOut('slow');
        $('#preloader').fadeOut('slow');
    })
</script>
<div id="preloader">
    <div id="status">Wait...</div>
</div>


<!-- Chart part -->

<table id="chart">
    <tr>
        <th style="width: 80%;">
            <b>{{ title }}</b>
        </th>
        <th>
            <b>Info</b>
        </th>
    </tr>
    <tr>
        <td>
            <div id="candlestickChart" style="height: 800px; width: 100%;"></div>
        </td>
        <td>
            {% for line in info %}
                <pre>{{ line }}</pre>
            {% endfor %}
        </td>
    </tr>
</table>


<!-- Footer -->

<table>
    <tr>
        <th><b>Generated by <a href="https://github.com/Tim55667757/PriceGenerator">PriceGenerator</a></b></th>
    </tr>
</table>


</body>

</html>
"""


class PriceGenerator:
    """
    This class implements methods to generation of prices statistically similar to real ones.

    **Model generated: OHLCV-candlesticks (open, high, low, close, volume).**
    """

    def __init__(self):
        """Main class init."""
        self.prices = None
        """Generated or loaded prices will be available in this Pandas DataFrame variable."""

        self.csvHeaders = ["date", "time", "open", "high", "low", "close", "volume"]
        """Headers in .CSV-file. Default: `["date", "time", "open", "high", "low", "close", "volume"]`."""

        self.dfHeaders = ["datetime", "open", "high", "low", "close", "volume"]
        """Headers in Pandas DataFrame. Default: `["datetime", "open", "high", "low", "close", "volume"]`."""

        self.sep = ","
        """Separator in csv - file. Default: `,`"""

        self.j2template = GOOGLE_TEMPLATE_J2
        """Full path to custom jinja2 html-template file (e.g. `google_template_example.j2`) or just set here a long multi-string variable. Default: `GOOGLE_TEMPLATE_J2` is a multi-string variable with internal template."""

        self.j2model = None
        """Dictionary of variables for jinja2 template. If `None` then used default variables for internal `GOOGLE_TEMPLATE_J2`"""

        self._precision = 2
        """Signs after comma. Default: `2`."""

        self._deg10prec = 100
        """Constant 10^precision is used by some formulas. Not recommended to change it. Default: `100` (`10 ** precision`)."""

        self.ticker = "TEST"
        """Some fake ticker name. Default: `Test`."""

        self.timeframe = timedelta(hours=1)
        """Time delta between two neighbour candles. Default: `timedelta(hours=1)`."""

        self.timeStart = datetime.now(tzlocal()).replace(microsecond=0, second=0, minute=0)
        """First date and time for candles chain."""

        self.horizon = None
        """Candlesticks count in generated or loaded chain of prices, must be >= 5. Default: `None` (means auto-detect length of chain if loaded from file)."""

        self.trendSplit = ""
        r"""Set different trends, e.g. `trendSplit="/\-"` means that generated candles has uptrend at first part, next downtrend and then no trend. Used only together with `splitCount` variable. Also, you can use words: `up`, `down`, `no` or chars: `u`, `d`, `n` with the hyphen symbol as separator, e.g. `trendSplit=up-down-no-up`, `trendSplit=u-d-n-u` etc. Default: `""`, empty string mean that will be used random trend directions."""

        self.splitCount = []
        """Set candles count in different trends, e.g. `splitCount=[5, 10, 15]` means that generated candles has 3 trends with 5, 10 and 15 candles in chain, with sum must be equal to horizon. Used only together with `trendSplit` variable. Default: `[]`, empty list mean that will be used random candles count in trends."""

        self.maxClose = random.uniform(70, 90)
        """Maximum of close prices must be >= `minClose`. Default: random in interval `(70, 90)`."""

        self.minClose = random.uniform(60, 70)
        """Minimum of close prices must be <= `maxClose`. Default: random in interval `(60, 70)`."""

        self.initClose = None
        """First candle close price value. If `None` then used random number in interval between `minClose` and `maxClose`. Default: `None`."""

        self.maxOutlier = None
        """Maximum size of outliers. If `None` then used value `(maxClose - minClose) / 10`. Default: `None`."""

        self.maxCandleBody = None
        """Maximum of candle body sizes: `abs(open - close)`. If `None` then used value `maxOutlier * 90%`. Default: `None`."""

        self._maxVolume = random.randint(1, 100000)
        """Maximum of generated trade volumes. Default: random in interval `[1, 100000]`."""

        self._upCandlesProb = 0.5
        """Probability that next candle is up. Default: `0.5` (means 50% of probability)."""

        self._outliersProb = 0.03
        """Outlier probability (price tails). Default: `0.03` (means 3% of probability)."""

        self._trendDeviation = 0.005
        """Relative deviation for trend detection. "NO trend" if `(1st_close - last_close) / 1st_close <= self.trendDeviation`. Default: `0.005` (means ±0.5% of price deviation)."""

        self._chartTitle = ""
        """Chart title. It will be auto-generated when loading or creating chain of candlesticks."""

        self._zigZagDeviation = 0.03
        """Relative deviation to detection next points used by Zig-Zag indicator. Default: `0.03` (means 3% of price deviation)."""

        self._stat = {
            "candles": 0,  # generated candlesticks count
            "precision": 2,  # generated candlesticks count
            "closeFirst": 0.,  # first close price
            "closeLast": 0.,  # last close price
            "closeMax": 0.,  # max close price
            "closeMix": 0.,  # min close price
            "diapason": 0.,  # diapason = closeMax - closeMin
            "trend": "NO trend",  # "UP trend" or "DOWN trend" with uses ±self.trendDeviation
            "trendDev": 0.005,
            "upCount": 0,  # count of up candles
            "downCount": 0,  # count of down candles
            "upCountChainMax": 0,  # max chain count of up candles
            "downCountChainMax": 0,  # max chain count of down candles
            "deltas": {
                "max": 0.,  # delta max = max(close_prices)
                "min": 0.,  # delta min = min(close_prices)
                "stDev": 0.,  # standard deviation
                "q99": 0.,  # 99 percentile
                "q95": 0.,  # 95 percentile
                "q80": 0.,  # 80 percentile
                "q50": 0.,  # 50 percentile
            },
            "cumSumVolumes": 0  # cumulative sum of volumes
        }
        """Some statistics available after candles loaded or generated."""

    @property
    def upCandlesProb(self):
        """Probability that next candle is up. Default: `0.5` (means 50% of probability)."""
        return self._upCandlesProb

    @upCandlesProb.setter
    def upCandlesProb(self, value):
        if value is None or value < 0:
            self._upCandlesProb = 0

        elif value > 1:
            self._upCandlesProb = 1

        else:
            self._upCandlesProb = value

    @property
    def outliersProb(self):
        """Outlier probability (price tails). Default: `0.03` (means 3% of probability)."""
        return self._outliersProb

    @outliersProb.setter
    def outliersProb(self, value):
        if value is None or value < 0:
            self._outliersProb = 0

        elif value > 1:
            self._outliersProb = 1

        else:
            self._outliersProb = value

    @property
    def trendDeviation(self):
        """Relative deviation for trend detection. "NO trend" if `(1st_close - last_close) / 1st_close <= self.trendDeviation`. Default: `0.005` (means ±0.5% of price deviation)."""
        return self._trendDeviation

    @trendDeviation.setter
    def trendDeviation(self, value):
        if value is None or value < 0:
            self._trendDeviation = 0

        elif value > 1:
            self._trendDeviation = 1

        else:
            self._trendDeviation = value

    @property
    def maxVolume(self):
        """Maximum of generated trade volumes. Default: random in interval `[1, 100000]`."""
        return self._maxVolume

    @maxVolume.setter
    def maxVolume(self, value):
        if value is None or value < 1:
            self._maxVolume = 1

        else:
            self._maxVolume = value

    @property
    def stat(self) -> dict:
        """Some statistics available after candles loaded or generated."""
        return self._stat

    @property
    def precision(self):
        """Signs after comma."""
        return self._precision

    @precision.setter
    def precision(self, value):
        self._precision = 2  # default
        self._deg10prec = 100  # default

        if isinstance(value, int):
            if value >= 0:
                self._precision = value
                self._deg10prec = 10 ** value  # 10^precision

    @property
    def zigZagDeviation(self):
        """Relative deviation to detection next points used by Zig-Zag indicator. Default: 0.03 (means 3% of price deviation)."""
        return self._zigZagDeviation

    @zigZagDeviation.setter
    def zigZagDeviation(self, value):
        if value is None or value < 0:
            self._zigZagDeviation = 0.03  # by default

        elif value > 1:
            self._zigZagDeviation = 1

        else:
            self._zigZagDeviation = value

    @staticmethod
    def FormattedDelta(tDelta: timedelta, fmt: str) -> str:
        """
        Pretty format for timedelta objects.

        Example: `FormattedDelta(timedelta(days=2, hours=3, minutes=15, seconds=35), "{days} days {hours}:{minutes}:{seconds}") -> "2 days 3:15:35"`.

        :return: timedelta object formatted as a string.
        """
        d = {"days": tDelta.days}
        d["hours"], rem = divmod(tDelta.seconds, 3600)
        d["minutes"], d["seconds"] = divmod(rem, 60)

        return fmt.format(**d)

    def DetectPrecision(self, examples: Union[np.ndarray, pd.Series, list]) -> int:
        """
        Auto-detect precision from example values. E.g. `0.123 -> 3`, `0.12345 -> 5` and so on.
        This method change `precision` variable after detect precision.

        See also about statistics.mode: https://docs.python.org/3.9/library/statistics.html#statistics.mode
        Changed in Python version >= 3.8: Now mode() method handles multimodal datasets by returning the first mode encountered.
        Previously, it raised StatisticsError when more than one mode was found.

        :param examples: chain with examples of float values.
        """
        uLogger.debug("Detecting precision of data values...")
        precision = 0
        try:
            precision = mode(list(map(lambda x: len(str(x).split('.')[-1]) if len(str(x).split('.')) > 1 else 0, examples))) if self.precision >= 0 else 0

        except StatisticsError as e:
            uLogger.debug("Statistic mode() method return an error! Precision is set to 2 (default). StatisticsError: '{}'".format(e))
            precision = 2

        finally:
            uLogger.debug("Auto-detected precision: {}".format(precision))

        self.precision = precision

        return precision

    def DetectTimeframe(self) -> timedelta:
        """
        Auto-detect time delta between last two neighbour candles.

        :return: timedelta object, also saved to `timeframe`.
        """
        self.timeframe = min(
            self.prices.iloc[-1].datetime - self.prices.iloc[-2].datetime,
            self.prices.iloc[-2].datetime - self.prices.iloc[-3].datetime
        )
        uLogger.debug("Auto-detected timeframe: {}".format(self.timeframe))

        return self.timeframe

    def LoadFromFile(self, fileName: str) -> pd.DataFrame:
        """
        Create Pandas OHLCV-model from CSV-file.
        Default columns in CSV-file are `["date", "time", "open", "high", "low", "close", "volume"]`.

        :param fileName: path to CSV-file with OHLCV columns.
        :return: Pandas DataFrame.
        """
        uLogger.info("Loading, parse and preparing input data from [{}]...".format(os.path.abspath(fileName)))

        self.prices = pd.read_csv(fileName, names=self.csvHeaders, engine="python", sep=self.sep, parse_dates={"datetime": ["date", "time"]})
        if self.horizon is None or self.horizon < 1 or self.horizon > len(self.prices):
            self.horizon = len(self.prices)  # use loaded file "as is" with all candles

        else:
            self.prices = self.prices.tail(self.horizon)  # remove old candles, leave only the "tail" ...
            self.prices.index = range(self.horizon)  # ... and reindex

        self.ticker = os.path.basename(fileName)

        self.DetectTimeframe()  # auto-detect time delta between last two neighbour candles

        uLogger.info("It was read {} rows".format(self.horizon))
        uLogger.info("Showing last 5 rows as Pandas DataFrame:")
        for line in pd.DataFrame.to_string(self.prices[self.dfHeaders][-5:], max_cols=20).split("\n"):
            uLogger.info(line)

        return self.prices

    def SaveToFile(self, fileName: str) -> None:
        """
        Save Pandas OHLCV model to CSV-file.

        :param fileName: path to CSV-file.
        """
        if self.prices is not None and not self.prices.empty:
            uLogger.info("Saving [{}] rows of Pandas DataFrame with columns: {}...".format(len(self.prices), self.csvHeaders))
            uLogger.debug("Delimeter: {}".format(self.sep))
            dataReplacedDateTime = self.prices.copy(deep=True)
            dataReplacedDateTime["date"] = [d.date() for d in dataReplacedDateTime["datetime"]]
            dataReplacedDateTime["time"] = [d.time() for d in dataReplacedDateTime["datetime"]]
            del dataReplacedDateTime["datetime"]
            dataReplacedDateTime = dataReplacedDateTime[self.csvHeaders]
            dataReplacedDateTime.to_csv(fileName, sep=self.sep, index=False, header=False)
            uLogger.info("Pandas DataFrame saved to .CSV-file [{}]".format(os.path.abspath(fileName)))

        else:
            raise Exception("Empty price data! Generate or load prices before saving!")

    @staticmethod
    def GetTrend(firstClose: float, lastClose: float, trendDeviation: float = 0.005) -> str:
        """
        Get string with trend: `"UP trend"`, `"DOWN trend"` or `"NO trend"`.

        :param firstClose: close of first candle.
        :param lastClose: close of last candle.
        :param trendDeviation: relative deviation for trend detection, 0.005 mean ±0.5% by default.
        :return: string with trend direction `"NO trend"`, `"UP trend"` or `"DOWN trend"`.
        """
        if abs(firstClose - lastClose) / firstClose <= trendDeviation:
            trend = "NO trend"

        else:
            trend = "UP trend" if firstClose <= lastClose else "DOWN trend"

        return trend

    @staticmethod
    def ZigZagFilter(datetimes: pd.Series, values: Union[pd.Series, list], deviation: float) -> pd.DataFrame:
        """
        This method filter input data as Zig-Zag indicator: when input value of candlestick price (e.g. close price)
        is difference with next values with define percent then this point is a point of Zig-Zag indicator.

        :param datetimes: input Pandas Series with datetime values.
        :param values: input Pandas Series or list, e.g. list of closes values of candlesticks.
        :param deviation: float number in `[0, 1]` interval is a relative difference between `i` and `i + 1` values to set as Zig-Zag point.
        :return: Pandas DataFrame with two Series of filtered data `"datetimes": filtered_datetimes` and `"filtered": filtered_values`.
        """
        filteredPoints = [True]
        prev = values[0]
        for i in range(1, len(values)):
            difference = abs(values[i] - prev) / prev
            if difference >= deviation:
                filteredPoints.append(True)
                prev = values[i]

            else:
                filteredPoints.append(False)

        return pd.DataFrame(data={"datetimes": datetimes[filteredPoints], "filtered": values[filteredPoints]}, columns=["datetimes", "filtered"])

    def GetStatistics(self) -> list[str]:
        """
        Calculates statistics of candles chain.

        :return: list with text in Markdown format with statistics.
        """

        ta = _LoadOptionalDependency("pandas_ta_classic", "indicators", "GetStatistics")

        uLogger.debug("Calculating column with deltas between high and low values...")
        self.prices["delta"] = self.prices.high.values - self.prices.low.values

        uLogger.debug("Calculating column with average values...")
        self.prices["avg"] = round((self.prices.high + self.prices.low) / 2, self._precision)

        uLogger.debug("Calculating some technical analysis indicators...")
        self.prices["sma5"] = ta.sma(close=self.prices.close, length=5, offset=None)
        self.prices["sma20"] = ta.sma(close=self.prices.close, length=20, offset=None)
        self.prices["sma50"] = ta.sma(close=self.prices.close, length=50, offset=None)
        self.prices["sma200"] = ta.sma(close=self.prices.close, length=200, offset=None)
        self.prices["hma5"] = ta.hma(close=self.prices.close, length=5, offset=None)
        self.prices["hma20"] = ta.hma(close=self.prices.close, length=20, offset=None)
        self.prices["vwma5"] = ta.vwma(close=self.prices.close, volume=self.prices.volume, length=5, offset=None)
        self.prices["vwma20"] = ta.vwma(close=self.prices.close, volume=self.prices.volume, length=20, offset=None)
        bbands = ta.bbands(close=self.prices.close, length=None, std=None, mamode=None, offset=None)
        bbands.columns = ["lower", "mid", "upper", "bandwidth", "percent"]
        psar = ta.psar(high=self.prices.high, low=self.prices.low, close=self.prices.close, af=0.02, max_af=0.2, offset=None)
        psar.columns = ["long", "short", "af", "reversal"]
        self.prices["hma13"] = ta.hma(close=self.prices.close, length=13, offset=8)  # alligator Jaw
        self.prices["hma8"] = ta.hma(close=self.prices.close, length=8, offset=5)  # alligator Teeth
        self.prices["hma5"] = ta.hma(close=self.prices.close, length=5, offset=3)  # alligator Lips
        zigzag = self.ZigZagFilter(datetimes=self.prices.datetime, values=self.prices.close, deviation=self.zigZagDeviation)  # ZigZag indicator

        self.DetectPrecision(self.prices.close.values)  # auto-detect precision

        self._chartTitle = "Instrument: {}, timeframe: {}, horizon length: {} (from {} to {})".format(
            self.ticker,
            self.FormattedDelta(
                self.timeframe, "{days} days {hours}h {minutes}m {seconds}s"
            ) if self.timeframe >= timedelta(days=1) else self.FormattedDelta(
                self.timeframe, "{hours}h {minutes}m {seconds}s"
            ),
            self.horizon,
            pd.to_datetime(self.prices.datetime.values[0]).strftime("%Y-%m-%d %H:%M:%S"),
            pd.to_datetime(self.prices.datetime.values[-1]).strftime("%Y-%m-%d %H:%M:%S"),
        )

        self._stat["candles"] = len(self.prices)
        self._stat["precision"] = self.precision
        self._stat["closeFirst"] = self.prices.close.values[0]
        self._stat["closeLast"] = self.prices.close.values[-1]
        self._stat["closeMax"] = max(self.prices.close)
        self._stat["closeMin"] = min(self.prices.close)
        self._stat["diapason"] = self._stat["closeMax"] - self._stat["closeMin"]
        self._stat["trend"] = self.GetTrend(firstClose=self._stat["closeFirst"], lastClose=self._stat["closeLast"], trendDeviation=self.trendDeviation)

        self.prices["up"] = self.prices.close >= self.prices.open  # True mean that is up candle, and False mean down
        upList = list(self.prices.up)
        upChainsLengths = [len(list(chain)) for value, chain in groupby(upList) if value is True]
        downChainsLengths = [len(list(chain)) for value, chain in groupby(upList) if value is False]

        self._stat["trendDev"] = self.trendDeviation
        self._stat["upCount"] = len(self.prices.up[self.prices.up == True])
        self._stat["downCount"] = len(self.prices.up[self.prices.up == False])
        self._stat["upCountChainMax"] = max(upChainsLengths) if upChainsLengths else 1
        self._stat["downCountChainMax"] = max(downChainsLengths) if downChainsLengths else 1
        self._stat["deltas"]["max"] = max(self.prices.delta)
        self._stat["deltas"]["min"] = min(self.prices.delta)
        self._stat["deltas"]["stDev"] = round(pstdev(self.prices.delta), self._precision)
        self._stat["deltas"]["q99"] = round(max(pd.DataFrame(self.prices.delta).quantile(q=0.99, interpolation='linear')), self._precision)
        self._stat["deltas"]["q95"] = round(max(pd.DataFrame(self.prices.delta).quantile(q=0.95, interpolation='linear')), self._precision)
        self._stat["deltas"]["q80"] = round(max(pd.DataFrame(self.prices.delta).quantile(q=0.80, interpolation='linear')), self._precision)
        self._stat["deltas"]["q50"] = round(max(pd.DataFrame(self.prices.delta).quantile(q=0.50, interpolation='linear')), self._precision)
        self._stat["cumSumVolumes"] = self.prices.volume.sum()

        self._stat["sma5"] = self.prices["sma5"]
        self._stat["sma20"] = self.prices["sma20"]
        self._stat["sma50"] = self.prices["sma50"]
        self._stat["sma200"] = self.prices["sma200"]
        self._stat["hma5"] = self.prices["hma5"]
        self._stat["hma20"] = self.prices["hma20"]
        self._stat["vwma5"] = self.prices["vwma5"]
        self._stat["vwma20"] = self.prices["vwma20"]
        self._stat["bbands"] = bbands
        self._stat["psar"] = psar
        self._stat["hma13"] = self.prices["hma13"]
        self._stat["hma8"] = self.prices["hma8"]
        self._stat["hma5"] = self.prices["hma5"]
        self._stat["zigzag3"] = zigzag

        summary = [
            "# Summary",
            "- Candles count: {}".format(self.stat["candles"]),
            "- Timeframe: {}".format(self.timeframe),
            "- Precision (signs after comma): {}".format(self.stat["precision"]),
            "- Close, first: {}".format(round(self.stat["closeFirst"], self.precision)),
            "- Close, last: {}".format(round(self.stat["closeLast"], self.precision)),
            "- Close, max: {}".format(round(self.stat["closeMax"], self.precision)),
            "- Close, min: {}".format(round(self.stat["closeMin"], self.precision)),
            "- Diapason, |close_max - close_min|: {}".format(round(self.stat["diapason"], self.precision)),
            "- Trend, |close_1st - close_last|: {}".format(self.stat["trend"]),
            "",
            "# Statistics",
            "- Up candles count: {} ({}%)".format(self.stat["upCount"], round(100 * self.stat["upCount"] / self.stat["candles"], self.precision)),
            "- Down candles count: {} ({}%)".format(self.stat["downCount"], round(100 * self.stat["downCount"] / self.stat["candles"], self.precision)),
            "- Max of up / down candle chains: {} / {}".format(self.stat["upCountChainMax"], self.stat["downCountChainMax"]),
            "- Max delta, |high - low|: {}".format(round(self.stat["deltas"]["max"], self.precision)),
            "- Min delta, |high - low|: {}".format(round(self.stat["deltas"]["min"], self.precision)),
            "- Delta's std. dev.: {}".format(round(self.stat["deltas"]["stDev"], self.precision)),
            "  - 99 percentile: ≤ {}".format(round(self.stat["deltas"]["q99"], self.precision)),
            "  - 95 percentile: ≤ {}".format(round(self.stat["deltas"]["q95"], self.precision)),
            "  - 80 percentile: ≤ {}".format(round(self.stat["deltas"]["q80"], self.precision)),
            "- Cumulative sum of volumes: {}".format(self.stat["cumSumVolumes"]),
        ]

        uLogger.info("Some statistics:\n{}".format("\n".join(summary)))

        return summary

    def _GenNextCandle(self, lastClose, lastVolume=0) -> dict:
        """
        Generator for creating 1 next candle based on global probability parameters.

        :param lastClose: value of the last close price.
        :param lastVolume: value of the last volume.
        :return: one OHLCV-candle as dict: {"open": lastClose, "high": newHigh, "low": newLow, "close": newClose, "volume": newVolume}.
        """
        candle = dict(open=lastClose, high=0., low=0., close=0., volume=0)  # init candle's object
        lastVolume = lastVolume if lastVolume > 0 else self.maxVolume // 2

        # Generating volume depends on the last value and outliers probability:
        volDelta = int(self.maxVolume * self.outliersProb)
        weight = lastVolume / self.maxVolume  # if w > 0.5 then more close to maxVolume, but else if w <= 0.5 then more close to 0
        volA = int(lastVolume - volDelta * (1 + weight))
        volB = int(lastVolume + volDelta * (1 + weight))
        volB = volB if 1 < volB <= self.maxVolume and volA > 0 else self.maxVolume
        volA = volA if volA > 0 else 1
        candle["volume"] = random.randint(a=volA, b=volB)

        if random.random() <= self.upCandlesProb:
            bodyUp = min(self.maxClose, candle["open"] + self.maxCandleBody)
            candle["close"] = round(random.uniform(a=candle["open"], b=bodyUp), self.precision)  # up candle
            halfBody = round(abs(candle["close"] - candle["open"]) / 2, self.precision)

            if random.random() <= self.outliersProb:
                candle["high"] = round(random.uniform(a=candle["close"], b=candle["close"] + self.maxOutlier), self.precision)  # with outlier high price

            else:
                candle["high"] = round(random.uniform(a=candle["close"], b=candle["close"] + halfBody), self.precision)  # without outlier

            if random.random() <= self.outliersProb:
                candle["low"] = round(random.uniform(a=candle["open"] - self.maxOutlier, b=candle["open"]), self.precision)  # with outlier low price

            else:
                candle["low"] = round(random.uniform(a=candle["open"] - halfBody, b=candle["open"]), self.precision)  # without outlier

        else:
            bodyDown = max(self.minClose, candle["open"] - self.maxCandleBody)
            candle["close"] = round(random.uniform(a=bodyDown, b=candle["open"]), self.precision)  # down candle
            halfBody = round(abs(candle["open"] - candle["close"]) / 2, self.precision)

            if random.random() <= self.outliersProb:
                candle["high"] = round(random.uniform(a=candle["open"], b=candle["open"] + self.maxOutlier), self.precision)  # with outlier high price

            else:
                candle["high"] = round(random.uniform(a=candle["open"], b=candle["open"] + halfBody), self.precision)  # without outlier

            if random.random() <= self.outliersProb:
                candle["low"] = round(random.uniform(a=candle["close"] - self.maxOutlier, b=candle["close"]), self.precision)  # with outlier high price

            else:
                candle["low"] = round(random.uniform(a=candle["close"] - halfBody, b=candle["close"]), self.precision)  # without outlier

        return candle

    def Generate(self) -> pd.DataFrame:
        """
        Main method to generating prices.

        :return Pandas DataFrame object with OHLCV-candlestick in every row and also saving it to the `prices`.
        """
        if self.horizon is None or self.horizon < 5:
            self.horizon = 5
            uLogger.debug("Horizon length less than 5! It is set to 5 by default.")

        if self.trendSplit is not None and self.splitCount is not None:
            # Detecting input trend:
            self.trendSplit = self.trendSplit.lower()
            if "/" in self.trendSplit or "\\" in self.trendSplit:
                uLogger.debug("Detected old-style string for split trend: {}".format(self.trendSplit))

                self.trendSplit = self.trendSplit.replace("-", "-no-").replace("/", "-up-").replace("\\", "-down-").replace("--", "-").lstrip("-").rstrip("-")

            else:
                uLogger.debug("Detected new-style string for split trend: {}".format(self.trendSplit))

                self.trendSplit = "-{}-".format(self.trendSplit)
                self.trendSplit = self.trendSplit.replace("-u-", "-up-").replace("-d-", "-down-").replace("-n-", "-no-").lstrip("-").rstrip("-")

            uLogger.debug("New style string for trend split is set: {}".format(self.trendSplit))

            trends = self.trendSplit.split("-")

            uLogger.debug("Trends list: {}".format(trends))

            if len(trends) > self.horizon:
                trends = trends[0]

                uLogger.debug("Trend parts count ({}) must be less than horizon ({})! New trend will be used: {}".format(len(trends), self.horizon, trends[0]))

            if sum(self.splitCount) != self.horizon or len(trends) == 1:
                self.splitCount = [self.horizon]

                uLogger.debug("Only one trend will be used with length equal to horizon: {}".format(self.splitCount))

            if len(self.splitCount) != len(trends):
                self.trendSplit = None
                self.splitCount = None

                uLogger.debug("Random trend direction will be used, because trends count not equal to split count!")

        else:
            trends = []

        # maximum of candle sizes: (high - low), if None then used (maxClose - minClose) / 10
        if self.maxOutlier is None:
            self.maxOutlier = abs(self.maxClose - self.minClose) / 10

        # maximum of candle body sizes: abs(open - close), if None then used maxOutlier * 90%
        if self.maxCandleBody is None:
            self.maxCandleBody = 0.9 * self.maxOutlier

        # initClose is the last close price (left on chart or "before" 1st generated candle), 1st candle["open"] = initClose
        if self.initClose is None:
            self.initClose = round(random.uniform(a=self.minClose, b=self.maxClose), self.precision)

        uLogger.info("Generating prices...")
        uLogger.debug("- Ticker name: {}".format(self.ticker))
        uLogger.debug("- Precision: {}".format(self.precision))
        uLogger.debug("- Interval or timeframe (time delta between two neighbour candles): {}".format(self.timeframe))
        uLogger.debug("- Horizon length (candlesticks count): {}".format(self.horizon))
        if self.trendSplit is not None and self.trendSplit and self.splitCount is not None and self.splitCount:
            uLogger.debug("- Trend type: {}".format(self.trendSplit))
            uLogger.debug("- Candlesticks count in every mini-trend: {}".format(self.splitCount))

        uLogger.debug("- Start time: {}".format(self.timeStart.strftime("%Y-%m-%d %H:%M:%S")))
        uLogger.debug("  |-> end time: {}".format((self.timeStart + self.horizon * self.timeframe).strftime("%Y-%m-%d %H:%M:%S")))
        uLogger.debug("- Maximum of close prices: {}".format(round(self.maxClose, self.precision)))
        uLogger.debug("- Minimum of close prices: {}".format(round(self.minClose, self.precision)))
        uLogger.debug("- Maximum of candle body sizes: {}".format(round(self.maxCandleBody, self.precision)))
        uLogger.debug("- Maximum of candle tails outlier sizes: {}".format(round(self.maxOutlier, self.precision)))
        uLogger.debug("- Init close (1st open price in chain): {}".format(round(self.initClose, self.precision)))
        uLogger.debug("- Maximum of volume of one candle: {}".format(self.maxVolume))
        uLogger.debug("- Probability that next candle is up: {}%".format(self.upCandlesProb * 100))
        uLogger.debug("- Statistical outliers probability: {}%".format(self.outliersProb * 100))

        # -- Preparing candles chain:
        if self.trendSplit is not None and self.trendSplit and self.splitCount is not None and self.splitCount:
            userProb = self.upCandlesProb
            userHorizon = self.horizon
            userInitC = self.initClose
            candles = []

            for trendNum in range(len(trends)):
                self.horizon = self.splitCount[trendNum]
                self.initClose = candles[-1]["close"] if trendNum > 0 else self.initClose

                # change probability of candles direction in next trend:
                if trends[trendNum] == "up":
                    self.upCandlesProb = 0.51 if userProb <= 0.5 else userProb

                elif trends[trendNum] == "down":
                    self.upCandlesProb = 0.49 if userProb >= 0.5 else userProb

                elif trends[trendNum] == "no":
                    self.upCandlesProb = 0.5

                else:
                    uLogger.error("Unknown direction used: {}".format(trends[trendNum]))

                    raise Exception("Unknown direction")

                firstCandle = self._GenNextCandle(round(self.initClose, self.precision), candles[-1]["volume"] if len(candles) > 0 else 0)  # first candle in next trend
                candles.append(firstCandle)

                for _ in range(1, self.horizon):
                    candles.append(self._GenNextCandle(candles[-1]["close"], candles[-1]["volume"]))

                highDelta = abs(candles[-1]["high"] - max(candles[-1]["open"], candles[-1]["close"]))  # save higher shadow
                lowDelta = abs(min(candles[-1]["open"], candles[-1]["close"]) - candles[-1]["low"])  # save lower shadow

                # -- Change last candle in every trend:
                if trends[trendNum] == "up":
                    if firstCandle["close"] >= candles[-1]["close"]:
                        candles[-1]["close"] = round(random.uniform(a=firstCandle["close"], b=self.maxClose), self.precision)

                elif trends[trendNum] == "down":
                    if firstCandle["close"] < candles[-1]["close"]:
                        candles[-1]["close"] = round(random.uniform(a=self.minClose, b=firstCandle["close"]), self.precision)

                else:  # if NO trend:
                    if abs(firstCandle["close"] - candles[-1]["close"]) / firstCandle["close"] > self.trendDeviation:
                        candles[-1]["close"] = round(
                            random.uniform(
                                a=firstCandle["close"] - firstCandle["close"] * self.trendDeviation / 2,
                                b=firstCandle["close"] + firstCandle["close"] * self.trendDeviation / 2,
                            ),
                            self.precision,
                        )

                candles[-1]["high"] = round(max(candles[-1]["open"], candles[-1]["close"]) + highDelta, self.precision)  # fixing higher shadow
                candles[-1]["low"] = round(min(candles[-1]["open"], candles[-1]["close"]) - lowDelta, self.precision)  # fixing lower shadow

            self.upCandlesProb = userProb
            self.horizon = userHorizon
            self.initClose = userInitC

        else:
            candles = [self._GenNextCandle(round(self.initClose, self.precision))]  # first candle in chain
            for _ in range(1, self.horizon):
                candles.append(self._GenNextCandle(candles[-1]["close"], candles[-1]["volume"]))

        # prepare Dataframe from generated prices:
        indx = pd.date_range(
            start=self.timeStart,
            end=self.timeStart + (self.horizon - 1) * self.timeframe,
            freq=self.timeframe,
            tz=tzlocal(),
        )
        self.prices = pd.DataFrame(data=candles, columns=self.dfHeaders)
        self.prices.datetime = indx

        uLogger.info("Showing last 5 rows of Pandas generated dataframe object:")
        for line in pd.DataFrame.to_string(self.prices[self.dfHeaders][-5:], max_cols=20).split("\n"):
            uLogger.info(line)

        return self.prices

    def RenderBokeh(
            self, fileName: Optional[str] = "index.html", viewInBrowser: bool = False,
            darkTheme: bool = False, markers: Optional[pd.DataFrame] = None, lines: Optional[list[pd.DataFrame]] = None,
            title: Optional[str] = None, width: Optional[int] = 1800, height: Optional[int] = 940,
            showControlsOnChart: bool = True, showStatOnChart: bool = True, inline: bool = False,
    ) -> Optional["LayoutDOM"]:
        """
        Rendering prices from Pandas DataFrame as OHLCV Bokeh chart of candlesticks and save it to HTML-file.
        Pandas DataFrame in `prices` variable must contain "datetime", "open", "high", "low", "close" and "volume" columns.

        See also: https://docs.bokeh.org/en/latest/docs/gallery/candlestick.html

        :param fileName: HTML-file path to save Bokeh chart. `index.html` by default.
        :param viewInBrowser: If `True`, then immediately opens HTML chart in browser after rendering. `False` by default.
        :param darkTheme: chart theme. `False` by default, mean that will be used light theme, `False` mean dark theme.
        :param markers: Pandas DataFrame with additional markers that will be placed on main series. `None` by default.
                        Marker is a custom symbol, example: ×, ↓ or ↑. Dataframe with markers must contain at least two columns.
                        There are `datetime` with date and time and some markers columns (`markersUpper`, `markersCenter` or `markersLower`).
                        Length of markers series must be equal to the length of main candles series.
        :param lines: list with custom series, where additional chart-lines will place on main series. `None` by default.
                      Line data must contain at least two columns. There are `datetime` with date and time and
                      `custom_line_name` with y-coordinates. Length of the chart-line dataframes must be equal to the length of main candle series.
        :param title: specific chart title. If `None`, then used auto-generated title. `None` by default.
        :param width: chart width. If `None`, then used auto-width. 1800 px by default.
        :param height: chart height. If `None`, then used auto-height. 940 px by default.
        :param showControlsOnChart: enable controls block in legend to hide/show some elements on chart, `True` by default.
        :param showStatOnChart: show statistics block on chart, `True` (by default) mean that will be calculating additional
                                series, like as Trend and Average Points. And some classical indicators, like as SMA, HMA,
                                VWMA, Bollinger Bands, Parabolic Stop and Reverse, Alligator and Zig-Zag indicator.
                                Warning! Calculate statistic takes more time. If you want to decrease chart rendering time,
                                then set this parameter to `False`.
        :param inline: if `True`, then output chart in Jupyter Notebook cell. `False` by default.
        :return: bokeh.layouts.gridplot with all layouts objects or None.
        """

        _LoadOptionalDependency("bokeh", "render", "RenderBokeh")
        from bokeh.plotting import figure, save, output_file, ColumnDataSource
        from bokeh.models import Legend, HoverTool, Range1d, NumeralTickFormatter
        from bokeh.layouts import gridplot
        from bokeh.io import output_notebook, show
        from bokeh.resources import INLINE

        if inline:
            _LoadOptionalDependency("IPython", "notebook", "RenderBokeh(inline=True)")
            _LoadOptionalDependency("ipykernel", "notebook", "RenderBokeh(inline=True)")

        if self.prices is None or self.prices.empty:
            raise Exception("Empty price data! Generate or load prices before show as Bokeh chart!")

        else:
            uLogger.info("Rendering Pandas DataFrame as Bokeh chart...")

            self.DetectTimeframe()  # auto-detect time delta between last two neighbour candles
            infoBlock = self.GetStatistics() if showStatOnChart else []  # calculating some indicators

            title = self._chartTitle if title is None or not title else title  # chart title
            width = 1200 if width is None or width <= 0 else width  # chart summary width
            height = 800 if height is None or height <= 0 else height - 90  # chart summary height

            uLogger.debug("Preparing Bokeh chart configuration...")
            uLogger.debug("Title: {}".format(title))

            if inline:
                output_notebook(resources=INLINE, verbose=False, hide_banner=True)  # set output to notebook cell

            # --- Preparing Main chart:
            chart = figure(
                title=title,
                x_axis_type="datetime",
                x_axis_label="Date and time",
                y_axis_label="Price",
                outline_line_width=3,
                outline_line_color="black" if darkTheme else "white",
                tools=["pan", "wheel_zoom", "box_zoom", "hover", "reset", "save"],
                toolbar_location="above",
                active_scroll="wheel_zoom",
                min_width=width,
                height=height,
                sizing_mode="scale_width",
                background_fill_color="black" if darkTheme else "white",
                min_border_left=0,
                min_border_right=0,
                min_border_top=0,
                min_border_bottom=0,
                y_range=Range1d(min(self.prices.low) - 3, max(self.prices.high) + 3),
            )
            chart.toolbar.logo = None  # remove bokeh logo and link to https://bokeh.org/
            chart.xaxis.major_label_orientation = pi / 6
            chart.grid.grid_line_dash = [6, 4]
            chart.grid.grid_line_alpha = 0.4
            chart.grid.minor_grid_line_dash = [6, 4]
            chart.grid.minor_grid_line_alpha = 0.4
            chart.xgrid.minor_grid_line_dash = [6, 4]
            chart.xgrid.minor_grid_line_alpha = 0.3
            chart.xgrid.minor_grid_line_color = "white" if darkTheme else "gray"
            chart.ygrid.minor_grid_line_dash = [6, 4]
            chart.ygrid.minor_grid_line_alpha = 0.3
            chart.ygrid.minor_grid_line_color = "white" if darkTheme else "gray"

            if showStatOnChart:
                summaryItems = [(info, []) for info in infoBlock]
                if showControlsOnChart:
                    summaryItems += [("", []), ("Click to show/hide on chart:", [])]

            else:
                summaryItems = [("Click to show/hide on chart:", [])] if showControlsOnChart else [("", [])]

            summaryInfo = Legend(
                click_policy="hide",
                items=summaryItems,
                location="top_right",
                label_text_font_size="8pt",
                margin=3,
                padding=2,
                spacing=-5,
                label_text_font="Lucida Console",
            )
            chart.add_layout(summaryInfo, "right")

            # preparing data for candles:
            inc = self.prices.open <= self.prices.close
            dec = self.prices.open > self.prices.close
            candleWidth = 108000  # as for 5 minutes by default

            if self.timeframe <= timedelta(days=31):
                candleWidth = 864000000  # 12 * 60 * 60 * 25 * 800  # for 43200 minutes

            if self.timeframe <= timedelta(days=7):
                candleWidth = 216000000  # 12 * 60 * 60 * 25 * 200  # for 10080 minutes

            if self.timeframe <= timedelta(days=1):
                candleWidth = 32400000  # 12 * 60 * 60 * 25 * 30  # for 1440 minutes

            if self.timeframe <= timedelta(hours=4):
                candleWidth = 6480000  # 12 * 60 * 60 * 25 * 6  # for 240 minutes

            if self.timeframe <= timedelta(hours=1):
                candleWidth = 1620000  # 12 * 60 * 60 * 25 * 1.5  # for 60 minutes

            if self.timeframe <= timedelta(minutes=30):
                candleWidth = 648000  # 12 * 60 * 60 * 15  # for 30 minutes

            if self.timeframe <= timedelta(minutes=15):
                candleWidth = 345600  # 12 * 60 * 60 * 8  # for 15 minutes

            if self.timeframe <= timedelta(minutes=5):
                candleWidth = 108000  # 12 * 60 * 60 * 2.5  # for 5 minutes

            if self.timeframe <= timedelta(minutes=1):
                candleWidth = 21600  # 12 * 60 * 30   # for 1 minute

            disabledObjects = []  # bokeh objects to hide by default when page is loaded

            # preparing data for hover tooltips:
            source = {
                "candle": [x + 1 for x in range(-len(self.prices.close), 0, 1)],
                "datetime": self.prices.datetime,
                "open": self.prices.open,
                "high": self.prices.high,
                "low": self.prices.low,
                "close": self.prices.close,
                "volume": self.prices.volume,
            }
            hoverData = ColumnDataSource(data=source)
            hover = chart.select(dict(type=HoverTool))
            hover.name = "candle"
            hover.tooltips = [
                ("Candle", "@candle"),
                ("Date", "@datetime{%Y-%m-%d}"),
                ("Time", "@datetime{%H:%M:%S}"),
                ("Open", "@open{0.0000}"),
                ("High", "@high{0.0000}"),
                ("Low", "@low{0.0000}"),
                ("Close", "@close{0.0000}"),
                ("Volume", "@volume"),
            ]
            hover.formatters = {
                "@datetime": "datetime",
                "@open": "numeral",
                "@high": "numeral",
                "@low": "numeral",
                "@close": "numeral",
            }
            hover.point_policy = "snap_to_data"
            hover.line_policy = "nearest"
            hover.mode = "vline"

            # --- preparing body of candles:
            hoverOnCandles = chart.segment(
                x0="datetime", y0="high", x1="datetime", y1="low",
                color="#20ff00" if darkTheme else "black",
                line_alpha=1, name="candle", source=hoverData,
            )
            hover.renderers = [hoverOnCandles]  # hover on only for candle bodies
            chart.vbar(
                x=self.prices.datetime[inc], width=candleWidth, bottom=self.prices.open[inc], top=self.prices.close[inc],
                fill_color="black" if darkTheme else "white", line_color="#20ff00" if darkTheme else "black",
                line_width=1, fill_alpha=1, line_alpha=1,
            )
            chart.vbar(
                x=self.prices.datetime[dec], width=candleWidth, bottom=self.prices.open[dec], top=self.prices.close[dec],
                fill_color="white" if darkTheme else "#999999", line_color="#20ff00" if darkTheme else "black",
                line_width=1, fill_alpha=1, line_alpha=1,
            )

            if showStatOnChart:
                # Summary section and controls:
                legendNameMain = "Max close / Min close / Trend line"
                legendNameAvg = "Averages points (highs - deltas/2)"
                legendNameSMA = "Simple Moving Averages (SMA: 5, 20)"
                legendNameSMAlong = "Long Simple Moving Averages (SMA: 50, 200)"
                legendNameHMA = "Hull Moving Averages (HMA: 5, 20)"
                legendNameVWMA = "Volume Weighted Moving Averages (VWMA: 5, 20)"
                legendNameBBANDS = "Bollinger Bands (BBands)"
                legendNamePsar = "Parabolic Stop and Reverse (psar)"
                legendNameAlligator = "Alligator (based on HMA: 13, 8, 5)"
                legendNameZigZag = "Zig-Zag indicator (with {}% of difference)".format(self.zigZagDeviation * 100)

                # preparing for highest close line:
                highestClose = round(max(self.prices.close.values), self._precision)
                chart.line(
                    self.prices.datetime, highestClose,
                    line_width=2, line_color="yellow" if darkTheme else "#339933", line_alpha=1,
                    legend_label=legendNameMain if showControlsOnChart else "",
                )
                chart.text(
                    self.prices.datetime.values[-1], highestClose + 1 / self._deg10prec,
                    text=[str(highestClose)], angle=0, text_color="yellow" if darkTheme else "#339933", text_font_size="9pt",
                    legend_label=legendNameMain if showControlsOnChart else "",
                )

                # preparing for lowest close line:
                lowestClose = round(min(self.prices.close.values), self._precision)
                chart.line(
                    self.prices.datetime, lowestClose,
                    line_width=2, line_color="yellow" if darkTheme else "#339933", line_alpha=1,
                    legend_label=legendNameMain if showControlsOnChart else "",
                )
                chart.text(
                    self.prices.datetime.values[-1], lowestClose - 2 / self._deg10prec,
                    text=[str(lowestClose)], angle=0, text_color="yellow" if darkTheme else "#339933", text_font_size="9pt",
                    legend_label=legendNameMain if showControlsOnChart else "",
                )

                # preparing direction lines for all trends:
                if self.trendSplit is not None and self.trendSplit and self.splitCount is not None and self.splitCount:
                    left = 0
                    for trendNum in range(len(self.splitCount)):
                        right = left + self.splitCount[trendNum] - 1
                        chart.line(
                            [self.prices.datetime.values[left], self.prices.datetime.values[right]],
                            [self.prices.close.values[left], self.prices.close.values[right]],
                            line_width=1, line_color="white" if darkTheme else "#666666", line_alpha=0.9, line_dash=[3, 3],
                            legend_label=legendNameMain if showControlsOnChart else "",
                        )
                        left += self.splitCount[trendNum]

                # preparing for main direction line:
                chart.line(
                    [self.prices.datetime.values[0], self.prices.datetime.values[-1]],
                    [self.prices.close.values[0], self.prices.close.values[-1]],
                    line_width=1, line_color="white" if darkTheme else "#666666", line_alpha=1, line_dash=[6, 6],
                    legend_label=legendNameMain if showControlsOnChart else "",
                )

                # preparing candle's average points:
                disabledObjects.append(chart.circle(
                    self.prices.datetime, self.prices.avg,
                    size=3, color="red", alpha=1,
                    legend_label=legendNameAvg if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.prices.avg,
                    line_width=1, line_color="red", line_alpha=1,
                    legend_label=legendNameAvg if showControlsOnChart else "",
                ))

                # --- Preparing a lot of TA lines:

                # Simple Moving Averages (SMA) 5, 20
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["sma5"],
                    line_width=2, line_color="yellow" if darkTheme else "#999432", line_alpha=1,
                    legend_label=legendNameSMA if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["sma20"],
                    line_width=3, line_color="red", line_alpha=1,
                    legend_label=legendNameSMA if showControlsOnChart else "",
                ))

                # Long Simple Moving Averages (SMA) 50, 200
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["sma50"],
                    line_width=2, line_color="#ffbf00", line_alpha=1,
                    legend_label=legendNameSMAlong if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["sma200"],
                    line_width=3, line_color="#ff0040", line_alpha=1,
                    legend_label=legendNameSMAlong if showControlsOnChart else "",
                ))

                # Hull Moving Averages (HMA) 5, 20
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["hma5"],
                    line_width=2, line_color="#00ffff" if darkTheme else "#336633", line_alpha=1,
                    legend_label=legendNameHMA if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["hma20"],
                    line_width=3, line_color="#ff00ff" if darkTheme else "#333333", line_alpha=1,
                    legend_label=legendNameHMA if showControlsOnChart else "",
                ))

                # Volume Weighted Moving Averages (VWMA) 5, 20
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["vwma5"],
                    line_width=2, line_color="blue" if darkTheme else "#666633", line_alpha=1,
                    legend_label=legendNameVWMA if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["vwma20"],
                    line_width=3, line_color="#ff8000" if darkTheme else "#333333", line_alpha=1,
                    legend_label=legendNameVWMA if showControlsOnChart else "",
                ))

                # Bollinger Bands (BBands)
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["bbands"]["lower"],
                    line_width=1, line_color="#66ffff" if darkTheme else "#333333", line_alpha=1,
                    legend_label=legendNameBBANDS if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["bbands"]["mid"],
                    line_width=1, line_color="#66ffff" if darkTheme else "#333333", line_alpha=1,
                    legend_label=legendNameBBANDS if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["bbands"]["upper"],
                    line_width=1, line_color="#66ffff" if darkTheme else "#333333", line_alpha=1,
                    legend_label=legendNameBBANDS if showControlsOnChart else "",
                ))

                # Parabolic Stop and Reverse (psar)
                disabledObjects.append(chart.circle(
                    self.prices.datetime, self.stat["psar"]["long"],
                    size=3, line_color="#00ffff" if darkTheme else "#336633", line_alpha=1,
                    legend_label=legendNamePsar if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.circle(
                    self.prices.datetime, self.stat["psar"]["short"],
                    size=3, line_color="#ff00ff" if darkTheme else "#663333", line_alpha=1,
                    legend_label=legendNamePsar if showControlsOnChart else "",
                ))

                # Alligator (based on HMA 13, 8, 5) for the Alligator indicator (Jaw, Teeth, and Lips)
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["hma13"],
                    line_width=2, line_color="#1a1aff" if darkTheme else "#2100A6", line_alpha=1,
                    legend_label=legendNameAlligator if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["hma8"],
                    line_width=2, line_color="#ff1a1a" if darkTheme else "#A6000C", line_alpha=1,
                    legend_label=legendNameAlligator if showControlsOnChart else "",
                ))
                disabledObjects.append(chart.line(
                    self.prices.datetime, self.stat["hma5"],
                    line_width=2, line_color="#40ff00" if darkTheme else "#17A600", line_alpha=1,
                    legend_label=legendNameAlligator if showControlsOnChart else "",
                ))

                # Zig-Zag indicator with self.zigZagDeviation of difference parameter
                disabledObjects.append(chart.line(
                    self.stat["zigzag3"]["datetimes"], self.stat["zigzag3"]["filtered"],
                    line_width=3, line_color="cyan" if darkTheme else "#333333", line_alpha=1,
                    legend_label=legendNameZigZag if showControlsOnChart else "",
                ))

                for item in disabledObjects:
                    item.visible = False

            # --- Preparing custom markers:

            if markers is not None and isinstance(markers, pd.DataFrame) and not markers.empty and len(markers.axes) >= 2 and "datetime" in markers.columns and ("markersUpper" in markers.columns or "markersCenter" in markers.columns or "markersLower" in markers.columns):
                if "markersUpper" in markers.columns:
                    chart.text(
                        markers.datetime.values, self.prices.high + 0.5,
                        text_align="center", text_baseline="bottom", text=markers.markersUpper.values,
                        angle=0, text_color="lime" if darkTheme else "black", text_font_size="13pt",
                        legend_label="Markers: upper ({})".format(len(markers.markersUpper[markers.markersUpper != ""])) if showControlsOnChart else "",
                    )

                if "markersCenter" in markers.columns:
                    if "avg" not in self.prices.columns:
                        self.prices["avg"] = round((self.prices.high + self.prices.low) / 2, self._precision)

                    chart.text(
                        markers.datetime.values, self.prices.avg,
                        text_align="center", text_baseline="middle", text=markers.markersCenter.values,
                        angle=0, text_color="red" if darkTheme else "black", text_font_size="13pt",
                        legend_label="Markers: center ({})".format(len(markers.markersCenter[markers.markersCenter != ""])) if showControlsOnChart else "",
                    )

                if "markersLower" in markers.columns:
                    chart.text(
                        markers.datetime.values, self.prices.low - 0.5,
                        text_align="center", text_baseline="top", text=markers.markersLower.values,
                        angle=0, text_color="lime" if darkTheme else "black", text_font_size="13pt",
                        legend_label="Markers: lower ({})".format(len(markers.markersLower[markers.markersLower != ""])) if showControlsOnChart else "",
                    )

            else:
                uLogger.debug("Marker data must be the Pandas DataFrame object! Or `None` (by default). Marker is a custom symbol, example: ×, ↓ or ↑. Dataframe with markers must contain at least two columns. There are `datetime` with date and time and some markers columns (`markersUpper`, `markersCenter` or `markersLower`). Length of markers series must be equal to the length of main candles series.")

            if not (showControlsOnChart or showStatOnChart):
                summaryInfo.visible = False

            # --- Preparing custom lines:

            if lines is not None and isinstance(lines, list) and lines:
                for line in lines:
                    if isinstance(line, pd.DataFrame) and len(line.axes) >= 2 and "datetime" in line.columns:
                        chart.line(
                            line.datetime, line[line.columns[1]],
                            line_width=3, line_color="red" if darkTheme else "#666666", line_alpha=1,
                            legend_label="Line: " + line.columns[1] if showControlsOnChart else "",
                        )

                    else:
                        uLogger.debug("Every custom line must be the Pandas DataFrame object! Line data must contain at least two columns: `datetime` with date and time and 2-nd column `custom_line_name` with y-coordinates. Length of the chart-line dataframes must be equal to the length of main candle series.")

            # --- Volume chart options:
            volumeChart = figure(
                x_axis_type="datetime",
                y_axis_label="Volume",
                outline_line_width=3,
                outline_line_color="black" if darkTheme else "white",
                min_width=width,
                height=90,
                sizing_mode="scale_width",
                background_fill_color="black" if darkTheme else "white",
                tools=["pan", "wheel_zoom", "hover"],
                toolbar_location=None,
                active_scroll="wheel_zoom",
                min_border_left=0,
                min_border_right=0,
                min_border_top=0,
                min_border_bottom=0,
                x_range=chart.x_range,
                y_range=Range1d(0, max(self.prices.volume), bounds=(0, max(self.prices.volume))),
            )
            volumeChart.toolbar.logo = None  # remove bokeh logo and link to https://bokeh.org/
            volumeChart.xaxis.major_label_orientation = pi / 6
            volumeChart.xaxis.visible = False
            volumeChart.yaxis.formatter = NumeralTickFormatter(format="0a")
            volumeChart.grid.grid_line_dash = [6, 4]
            volumeChart.grid.grid_line_alpha = 0.5
            volumeChart.grid.minor_grid_line_dash = [6, 4]
            volumeChart.grid.minor_grid_line_alpha = 0.5
            volumeChart.xgrid.minor_grid_line_dash = [6, 4]
            volumeChart.xgrid.minor_grid_line_alpha = 0.3
            volumeChart.xgrid.minor_grid_line_color = "white" if darkTheme else "gray"

            # preparing data for hover tooltips:
            volSource = {
                "candle": [x + 1 for x in range(-len(self.prices.close), 0, 1)],
                "datetime": self.prices.datetime,
                "volume": self.prices.volume,
                "zero": [0] * len(self.prices.volume),
            }
            volHoverData = ColumnDataSource(data=volSource)
            volHover = volumeChart.select(dict(type=HoverTool))
            volHover.name = "volumes"
            volHover.tooltips = [
                ("Candle", "@candle"),
                ("Date", "@datetime{%Y-%m-%d}"),
                ("Time", "@datetime{%H:%M:%S}"),
                ("Volume", "@volume"),
            ]
            volHover.formatters = {
                "@datetime": "datetime",
            }
            volHover.point_policy = "snap_to_data"
            volHover.line_policy = "nearest"
            volHover.mode = "vline"

            # preparing volume chart:
            hoverOnVolumes = volumeChart.segment(
                x0="datetime", y0="volume", x1="datetime", y1="zero",
                color="black", line_alpha=0, name="volumes", source=volHoverData,
            )
            volHover.renderers = [hoverOnVolumes]  # hover on only for volume bars
            volumeChart.vbar(
                x=self.prices.datetime[inc], width=candleWidth, bottom=0, top=self.prices.volume[inc],
                fill_color="black" if darkTheme else "white", line_color="#20ff00" if darkTheme else "black",
                line_width=1, fill_alpha=1, line_alpha=1,
            )
            volumeChart.vbar(
                x=self.prices.datetime[dec], width=candleWidth, bottom=0, top=self.prices.volume[dec],
                fill_color="white" if darkTheme else "#999999", line_color="#20ff00" if darkTheme else "black",
                line_width=1, fill_alpha=1, line_alpha=1,
            )

            # Merge Main and Volume charts in one Bokeh gridplot object:
            unionChart = gridplot(
                children=[[chart], [volumeChart]],
                sizing_mode="stretch_both",
                merge_tools=False,
                width=width,
            )
            unionChart.toolbar.logo = None

            if inline:
                show(unionChart, notebook_handle=True)

            else:
                # preparing HTML-file chart and statistics in markdown:
                if fileName:
                    try:
                        output_file(fileName, title=title, mode="cdn")
                        save(unionChart, fileName)

                    except Exception as e:
                        uLogger.warning("Can't render HTML! Error message: {}".format(e))

                    else:
                        uLogger.info("Pandas DataFrame saved as HTML-file [{}]".format(os.path.abspath(fileName)))

                        if viewInBrowser:
                            webbrowser.open(Path(fileName).resolve().as_uri())

                    if showStatOnChart:
                        mdFile = "{}.md".format(fileName)
                        with open(mdFile, "w", encoding="UTF-8") as fH:
                            fH.write("\n".join(infoBlock))

                            uLogger.info("Statistics saved to [{}]".format(os.path.abspath(mdFile)))

            return unionChart

    def RenderGoogle(self, fileName: str = "index.html", viewInBrowser: bool = False, title: Optional[str] = None) -> None:
        """
        Rendering prices from Pandas DataFrame as non-interactive Google Candlestick chart and save it to HTML-file.

        See also: https://developers.google.com/chart/interactive/docs/gallery/candlestickchart

        :param fileName: HTML-file path to save Google Candlestick chart.
        :param viewInBrowser: If `True`, then immediately opens html in browser after rendering.
        :param title: specific chart title. If `None`, then used auto-generated title. `None` by default.
        """

        jinja2 = _LoadOptionalDependency("jinja2", "render", "RenderGoogle")

        if self.prices is None or self.prices.empty:
            raise Exception("Empty price data! Generate or load prices before show as Google Candlestick chart!")

        else:
            uLogger.info("Rendering Pandas DataFrame as Google Candlestick chart...")

            self.DetectTimeframe()  # auto-detect time delta between last two neighbour candles
            infoBlock = self.GetStatistics()  # calculating some indicators

            title = self._chartTitle if title is None or not title else title  # chart title

            if self.j2model is None or not self.j2model:
                uLogger.debug("Preparing Google Candlestick chart configuration...")
                self.j2model = {"info": infoBlock, "title": title}
                googleDates = [pd.to_datetime(date).strftime("%Y-%m-%d %H:%M:%S") for date in self.prices.datetime.values]
                data = zip(googleDates, self.prices.low, self.prices.open, self.prices.close, self.prices.high)
                self.j2model["candlesData"] = [list(x) for x in data]

            else:
                uLogger.debug("Using custom chart model")

            # --- Rendering and saving chart as HTML-file and markdown-file with statistics:
            if os.path.exists(self.j2template):
                renderedTemplate = jinja2.Template(open(self.j2template, "r", encoding="UTF-8").read())

            else:
                renderedTemplate = jinja2.Template(self.j2template)

            htmlMain = renderedTemplate.render(self.j2model)

            with open(fileName, "w", encoding="UTF-8") as fH:
                fH.write(htmlMain)
            with open("{}.md".format(fileName), "w", encoding="UTF-8") as fH:
                fH.write("\n".join(infoBlock))

            if viewInBrowser:
                webbrowser.open(Path(fileName).resolve().as_uri())

            uLogger.info("Pandas DataFrame rendered as HTML-file [{}]".format(os.path.abspath(fileName)))


def ParseArgs():
    """This function get and parse command line keys."""
    parser = ArgumentParser()  # command-line string parser

    parser.description = "PriceGenerator is the platform for generating prices similar to real stock prices, but you can control the statistics of their distribution. Generates chain of candlesticks with predefined statistical parameters, return Pandas DataFrame or saving as .CSV-file with OHLCV-candlestick in every string. Use PriceGenerator to generate synthetic data to test your trading strategy. See examples: https://tim55667757.github.io/PriceGenerator"
    parser.usage = "\n/as module/ python PriceGenerator.py [some options] [one command]\n/as CLI tool/ pricegenerator [some options] [one command]"

    # options:
    parser.add_argument("--ticker", type=str, default="TEST", help="Option: some fake ticker name, 'TEST' by default.")
    parser.add_argument("--precision", type=int, default=2, help="Option: precision is count of digits after comma, 2 by default.")
    parser.add_argument("--timeframe", type=int, default=60, help="Option: time delta between two neighbour candles in minutes, 60 (1 hour) by default.")
    parser.add_argument("--start", type=str, help="Option: start time of 1st candle as string with format 'year-month-day hour:min', e.g. '2021-01-02 12:00'.")
    parser.add_argument("--horizon", type=int, default=30, help="Option: candlesticks count. Default: 30.")
    parser.add_argument("--split-trend", type=str, default="", help=r"Option: set different trends, e.g. `--split-trend=/\-` means that generated candles has uptrend at first part, next downtrend and then no trend. Used only together with `--split-count` key. Also, you can use words: `up`, `down`, `no` or chars: `u`, `d`, `n` with the hyphen symbol as separator, e.g. `--split-trend=up-down-no-up`, `--split-trend=u-d-n-u` etc. Default: empty string, mean that will be used random trend directions.")
    parser.add_argument("--split-count", type=int, nargs="+", help="Option: set candles count in different trends, e.g. `--split-count 5 10 15` means that generated candles has 3 trends with 5, 10 and 15 candles in chain, with sum must be equal to `--horizon` value. Used only together with `--split-trend` key. Default: [], empty list mean that will be used random candles count in trends.")
    parser.add_argument("--max-close", type=float, help="Option: maximum of all close prices.")
    parser.add_argument("--min-close", type=float, help="Option: minimum of all close prices.")
    parser.add_argument("--init-close", type=float, help="Option: generator started 1st open price equal to this last close price.")
    parser.add_argument("--max-outlier", type=float, help="Option: maximum of outlier size of candle tails, by default used (max_close - min_close) / 10.")
    parser.add_argument("--max-body", type=float, help="Option: maximum of candle body sizes: abs(open - close), by default used max_outlier * 0.9.")
    parser.add_argument("--max-volume", type=int, help="Option: maximum of trade volumes.")
    parser.add_argument("--up-candles-prob", type=float, default=0.5, help="Option: float number in [0; 1] is a probability that next candle is up, 0.5 by default.")
    parser.add_argument("--outliers-prob", type=float, default=0.03, help="Option: float number in [0; 1] is an outliers probability (price tails), 0.03 by default.")
    parser.add_argument("--trend-deviation", type=float, default=0.005, help="Option: relative deviation for trend detection, 0.005 mean ±0.005 by default. No trend if (1st_close - last_close) / 1st_close <= trend_deviation.")
    parser.add_argument("--zigzag", type=float, default=0.03, help="Option: relative deviation to detection points of Zig-Zag indicator, 0.03 by default.")
    parser.add_argument("--sep", type=str, default=None, help="Option: separator in CSV-file, if None then auto-detecting enable.")
    parser.add_argument("--dark", action="store_true", default=False, help="Option: if key present, then will be used dark theme for the `--render-bokeh` key. `False` by default for light theme.")
    parser.add_argument("--debug-level", type=int, default=20, help="Option: showing STDOUT messages of minimal debug level, e.g., 10 = DEBUG, 20 = INFO, 30 = WARNING, 40 = ERROR, 50 = CRITICAL.")

    # commands:
    parser.add_argument("--load-from", type=str, help="Command: load .cvs-file to Pandas DataFrame. You can draw chart in additional with `--render-bokeh` or `--render-google` key.")
    parser.add_argument("--generate", action="store_true", help="Command: generates chain of candlesticks with predefined statistical parameters and save stock history as Pandas DataFrame or .CSV-file if `--save-to` key is defined. You can draw chart in additional with `--render-bokeh` or `--render-google` keys.")
    parser.add_argument("--save-to", type=str, help="Command: save generated or loaded dataframe to .CSV-file. You can draw chart in additional with `--render-bokeh` or `--render-google` keys.")
    parser.add_argument("--render-bokeh", type=str, help="Command: show chain of candlesticks as interactive Bokeh chart. Used only together with `--load-from` or `--generate` keys.")
    parser.add_argument("--render-google", type=str, help="Command: show chain of candlesticks as non-interactive Google Candlestick chart. Used only together with `--load-from` or `--generate` keys.")

    cmdArgs = parser.parse_args()
    return cmdArgs


def Main():
    """
    Main function for work with PriceGenerator in the console.

    See examples:
    - in english: https://github.com/Tim55667757/PriceGenerator/blob/master/README.md
    - in russian: https://github.com/Tim55667757/PriceGenerator/blob/master/README_RU.md

    [![gift](https://badgen.net/badge/gift/donate/green)](https://yoomoney.ru/fundraise/BxB9DQNvJnk.230111)
    """
    args = ParseArgs()  # get and parse command-line parameters
    exitCode = 0

    if args.debug_level:
        uLogger.level = 10  # always debug level by default
        uLogger.handlers[0].level = args.debug_level  # level for STDOUT
        # uLogger.handlers[1].level = 10  # always debug level for log.txt

    start = datetime.now(tzlocal())
    uLogger.debug(uLog.sepLine)
    uLogger.debug("PriceGenerator started: {}".format(start.strftime("%Y-%m-%d %H:%M:%S")))

    priceModel = PriceGenerator()

    try:
        # --- set options:

        if args.sep:
            priceModel.sep = args.sep  # separator in .CSV-file

        if args.ticker:
            priceModel.ticker = args.ticker  # some fake ticker name, "TEST" by default

        if int(args.precision) >= 0:
            priceModel.precision = args.precision  # precision is count of digits after comma, 2 by default

        if args.timeframe:
            priceModel.timeframe = timedelta(minutes=args.timeframe)  # time delta between two neighbour candles in minutes, 60 (1 hour) by default

        if args.start:
            priceModel.timeStart = pd.to_datetime(args.start, format="%Y-%m-%d %H:%M")

        if args.horizon:
            priceModel.horizon = args.horizon  # generating candlesticks count

        if args.split_trend:
            priceModel.trendSplit = args.split_trend  # difference periods

        if args.split_count:
            priceModel.splitCount = args.split_count  # candles in every period

        if args.max_close:
            priceModel.maxClose = args.max_close  # maximum of all close prices

        if args.min_close:
            priceModel.minClose = args.min_close  # minimum of all close prices

        if args.init_close:
            priceModel.initClose = args.init_close  # generator started 1st open price of chain from this "last" close price

        if args.max_outlier:
            priceModel.maxOutlier = args.max_outlier  # maximum of outlier size of candle tails, by default used (max-close - min-close) / 10

        if args.max_body:
            priceModel.maxCandleBody = args.max_body  # maximum of candle body sizes: abs(open - close), by default used max-outlier * 90%

        if args.max_volume:
            priceModel.maxVolume = args.max_volume  # maximum of trade volumes

        if args.up_candles_prob:
            priceModel.upCandlesProb = args.up_candles_prob  # float number in [0; 1] is a probability that next candle is up, 0.5 = 50% by default

        if args.outliers_prob:
            priceModel.outliersProb = args.outliers_prob  # float number in [0; 1] is a statistical outlier probability (price "tails"), 0.03 = 3% by default

        if args.trend_deviation:
            priceModel.trendDeviation = args.trend_deviation  # relative deviation for trend detection, 0.005 mean ±0.5% by default. "NO trend" if (1st_close - last_close) / 1st_close <= trend-deviation

        if args.zigzag:
            priceModel.zigZagDeviation = args.zigzag  # relative deviation to detection points of ZigZag indicator, 0.03 by default

        # --- do one or more commands:

        if not args.load_from and not args.generate and not args.save_to and not args.render_bokeh:
            raise Exception("At least one command must be selected! See: python PriceGenerator.py --help")

        if args.load_from:
            priceModel.LoadFromFile(fileName=args.load_from)

        if args.generate:
            priceModel.Generate()

        if args.save_to:
            priceModel.SaveToFile(fileName=args.save_to)

        if args.render_bokeh:
            priceModel.RenderBokeh(
                fileName=args.render_bokeh,
                viewInBrowser=True,
                darkTheme=args.dark,
                width=1800,
                height=940,
                showControlsOnChart=True,
                showStatOnChart=True,
                inline=False,
            )

        if args.render_google:
            priceModel.RenderGoogle(
                fileName=args.render_google,
                viewInBrowser=True,
            )

    except Exception as e:
        uLogger.error(e)
        exc = tb.format_exc().split("\n")
        for line in exc:
            if line:
                uLogger.debug(line)
        exitCode = 255

    finally:
        finish = datetime.now(tzlocal())

        if exitCode == 0:
            uLogger.debug("All PriceGenerator operations are finished success (summary code is 0).")

        else:
            uLogger.error("An errors occurred during the work! See full debug log with --debug-level 10. Summary code: {}".format(exitCode))

        uLogger.debug("PriceGenerator work duration: {}".format(finish - start))
        uLogger.debug("PriceGenerator work finished: {}".format(finish.strftime("%Y-%m-%d %H:%M:%S")))

        sys.exit(exitCode)


if __name__ == "__main__":
    Main()
