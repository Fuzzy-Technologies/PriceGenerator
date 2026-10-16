# PriceGenerator — Release notes

[Русский](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/develop/CHANGELOG_RU.md) ·
[Documentation](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/develop/README.md) ·
[Release procedure](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/develop/docs/releasing.md)

## 2.0.0

This is an intentionally breaking replacement of the 1.x runtime. Publication
is a separate operation; the [PyPI project](https://pypi.org/project/pricegenerator/)
and release workflow record its actual status. Historical release entries below
retain their original provenance.

- **API, model and CLI:** immutable `GenerationConfig` and `Generate(config)`
  replace the mutable class. `regime_v2` owns a private seeded RNG, fixed UTC
  defaults, explicit drift/regimes, independent shock and wick events, bounded
  positive prices and continuous volume. Seed zero works. There is no runtime
  legacy model, compatibility class or old CLI flag alias; old seeds are not a
  promise of identical v2 sequences. Commands are `generate`, `replay`,
  `validate`, `analyze` and `chart`.
- **Data and reproducibility:** strict six-column headered OHLCV CSV, UTC
  nanosecond timestamps, finite float64 values, detached validation and explicit
  timezone/cadence policies. Manifests record complete inputs, model/RNG/library
  and environment identity, a scenario fingerprint and a separate exact output
  fingerprint. Portable replay still verifies both hashes. Development-version
  manifests retain their original library identity rather than being silently
  relabeled as 2.0.0. `GenerateChunks`/`WriteCSVChunks` provide bounded-memory
  streaming with the same generation sequence.
- **Analysis and research:** nonmutating diagnostics and modern NumPy/pandas
  indicator formulas replace the TA backend. HMA and Alligator are separate;
  warmup/undefined estimates remain explicit. Module-qualified calibration,
  comparisons, bootstrap/scripted scenarios and model registry helpers remain
  experimental. Recorded synthetic invariants, event frequencies and historical
  comparisons do not establish universal market realism, forecasts or strategy
  profitability.
- **Charts:** `Chart` defaults to self-contained interactive HTML and browser
  viewing; use `view=False` for automation. SVG is available in core; optional
  `[export]` adds Python PNG/JPEG through pinned resvg-py/Pillow. `DisplayChart`
  embeds HTML in notebooks. Analysis overlays require `analysis=True`. Both
  engines preserve the main emblem and show exactly one translucent corporate
  wordmark in the price panel, none in volume. Assets and notices work offline.
- **Packaging and release:** CPython 3.10–3.13; NumPy, pandas and python-dateutil
  form the core dependency set. Bokeh, Jinja and pandas-ta are absent. Exact
  constraints, wheel/sdist clean installs and actual raster-export checks feed
  GitHub Actions. Manual tagged-master release verification requires green
  quality/Canvas evidence; protected environment approval precedes attested PyPI
  Trusted Publishing. Travis uploads are removed. Publication still requires
  the configured external publisher and approval.

See the [migration guide](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/develop/docs/chart-migration.md),
[model contract](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/develop/docs/model-regime-v2.md)
and [ADR-0010](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/develop/docs/adr/0010-modern-only-public-api.md).
Historical 1.x source and baseline evidence remain archived, outside the modern
runtime and active dependency requirements.


### [1.4.93 (2023-11-25)](https://github.com/Tim55667757/PriceGenerator/releases/tag/v1.4.93) — released

##### Digest

Now the volume values depends on the previous value and outliers probability and looks more realistic. The generator algorithm creates a series of candles better for difficult trends, include differ outliers for upper and lower shadows of candles and its bodies. Also, bugs with negative numbers in series should no longer appear.

Example of the long-time series with realistic dispersion of volume values and differ trends:

![image](https://raw.githubusercontent.com/Tim55667757/PriceGenerator/develop/media/long-series-example-with-realistic-volumes.png)

##### New features

* The generator algorithm mow creates a series of candles better for difficult trends, include differ outliers for upper and lower shadows of candles.

##### Improvements

* [#22](https://github.com/Tim55667757/PriceGenerator/issues/22) Type of `ZigZagFilter()` was changed to Pandas Dataframe instead of dict.
* [#25](https://github.com/Tim55667757/PriceGenerator/issues/25) Volume values now depend on the previous value and outliers probability.

##### Bug fixes

* [#24](https://github.com/Tim55667757/PriceGenerator/issues/24) Bug fix with negative numbers in series.


### [1.3.81 (2023-01-05)](https://github.com/Tim55667757/PriceGenerator/releases/tag/1.3.81) — released

##### Digest

**WARNING!** Python supported version was changed to 3.9.
 
Now you can draw an additional custom lines and markers on main chart with candles (using `RenderBokeh()` method). You can specify trend directions with simple words: `up`, `down`, `no` or chars: `u`, `d`, `n`, when using `--split-trend` key (in addition to the existing ability to identify trend with symbols `/\-`), e.g. `--split-trend=up-down-no-up`, `--split-trend=u-d-n-u` etc. Also, you can choose themes for charts drawn by `RenderBokeh()` method with the new parameter `darkTheme` (if `True` then using dark theme, else light theme).

Light style example (with some custom markers and new average line):

![image](https://user-images.githubusercontent.com/7660870/210442177-a7d9f2bd-e426-43bb-bf5d-bf66339ea56e.png)

Dark style example (with some custom markers):

![image](https://user-images.githubusercontent.com/7660870/210591393-3f36cb5f-a8fd-4c3c-a085-23177c8c464d.png)

##### New features

* Python version support was changed to 3.9.
* [#17](https://github.com/Tim55667757/PriceGenerator/issues/17) Into the `RenderBokeh()` method was added `layouts` parameter. You can add new Bokeh Chart-objects on the Main Chart with that parameter. Also, `darkTheme` parameter was added. If it `True`, then will be used dark theme, `False` (by default) mean light theme. Also, you can manipulate with chart and adding lines or markers to the main chart. Use `markers` and `lines` parameters for it. `markers` is a Pandas Dataframe with custom series, where additional markers will place on main series. `None` by default. One marker is a custom symbol, e.g. ×, ↓ or ↑ or anyone else. Marker data must contain at least two columns. There are `datetime` with date and time and some markers columns (`markersUpper`, `markersCenter` or `markersLower`). Length of marker dataframes must be equal to the length of main candle series. `lines` is a list with custom series, where additional chart-lines will place on main series. `None` by default. Line data must contain at least two columns. There are `datetime` with date and time and `custom_line_name` with y-coordinates. Length of the chart-line dataframes must be equal to the length of main candle series.
* [#10](https://github.com/Tim55667757/PriceGenerator/issues/10) Ability to specify directions with words or chars was added. Words may be next: `up`, `down`, `no` or chars: `u`, `d`, `n` for the `--split-trend` key, in addition to the existing ability to set up of the trend with symbols `/\-`. To separate words or chars use the hyphen symbol, e.g. `--split-trend=up-down-no-up`, `--split-trend=u-d-n-u` etc.
* [#13](https://github.com/Tim55667757/PriceGenerator/issues/13) [API-doc](https://tim55667757.github.io/PriceGenerator/docs/pricegenerator/PriceGenerator.html) on module `PriceGenerator` was added.

##### Improvements

* [#15](https://github.com/Tim55667757/PriceGenerator/issues/15) Statistic block view was improvement.
* [#16](https://github.com/Tim55667757/PriceGenerator/issues/16) Examples were added: [how to generate prices chain without candles](https://github.com/Tim55667757/PriceGenerator/issues/16#issuecomment-1287875048).

##### Bug fixes

* [#19](https://github.com/Tim55667757/PriceGenerator/issues/19) Bug fix with incorrect high and low values when trend is set.
* [#18](https://github.com/Tim55667757/PriceGenerator/issues/18) Bug fix with incorrect multiple tips on chart and incorrect width of visible area.
* [#11](https://github.com/Tim55667757/PriceGenerator/issues/11) Incorrect warnings were disabled.


### [1.2.58 (2021-12-09)](https://github.com/Tim55667757/PriceGenerator/releases/tag/1.2.58) — released

##### New features

* License changed from MIT to [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).
* [#8](https://github.com/Tim55667757/PriceGenerator/issues/8) Added ability to separate candlesticks by some trends. It was implemented two additional keys: `--split-trend` and `--split-count`. These keys affect the appearance of the trend and the number of candles in each trend.
  * The `--split-trend` key shows trends movements, e.g. `--split-trend=/\-` means that generated candles has uptrend at first part, next downtrend and then no trend.
  * The `--split-count` key set count of candles of difference periods, e.g. `--split-count 5 10 15` means that generated candles has 3 trends with 5, 10 and 15 candles in chain.


### [1.2.46 (2021-02-28)](https://github.com/Tim55667757/PriceGenerator/releases/tag/1.2.46) — released

##### New features

* Some moving averages were added to Bokeh chart with [`pandas_ta`](https://github.com/Tim55667757/pandas-ta) library:
  * Simple Moving Averages (5, 20, 50, 200),
  * Hull Moving Averages (5, 20),
  * Volume Weighted Moving Averages (5, 20),
  * Also, only "Max_close / Min_close / Trend line" is showing by default.
* Volatility indicators were implements:
  * Bollinger Bands,
  * Parabolic Stop and Reverse,
  * Alligator (based on HMAs 13, 8, 5),
  * ZigZag with 3% deviation by default.
* Volume chart was added.
* Candle's tooltips were added on main and volume charts.

##### Improvements

* More tests and examples were added. Also, little refactor. All used libraries were updated.
* The key `--horizon` when loading from a file is used to specify loading of the last N = horizon candles.
* The `--precision` key is used to specify the signs after comma.

##### Bug fixes

* Not-detected timeframe when rendering from Pandas DataFrame without loading from file was fixed.


### [1.1.30 (2021-02-20)](https://github.com/Tim55667757/PriceGenerator/releases/tag/1.1.30) — released

##### New features

* A lot of keys were added for CLI: `--ticker`, `--timeframe`, `--start`, `--horizon`, `--max-close`, `--min-close`, `--init-close`, `--max-outlier`, `--max-body`, `--max-volume`, `--up-candles-prob`, `--outliers-prob`, `--trend-deviation`. That keys are overriding default parameters.
* Implements new method `RenderGoogle()` and a `--render-google` key that can draw not interactive [Google Candlestick Chart](https://developers.google.com/chart/interactive/docs/gallery/candlestickchart).

##### Improvements

* Extended examples were added. See examples in [`README.md`](https://github.com/Tim55667757/PriceGenerator/blob/master/README.md) (english) and [`README_RU.md`](https://github.com/Tim55667757/PriceGenerator/blob/master/README_RU.md) (russian).


### [1.0.19 (2021-02-05)](https://github.com/Tim55667757/PriceGenerator/releases/tag/1.0.19) — released

##### Retrospective

The first version of PriceGenerator library allows you to:
* save generated prices in csv-format (example: `./media/test.csv`);
* save the generated prices to a Pandas DataFrame variable for further use in automation scripts;
* automatically calculate some statistical and probabilistic characteristics of the generated prices and save them in Markdown format (example: `./media/index.html.md`);
* load the prices of real instruments according to the OHLCV-candlesticks model from the csv-file and carry out their statistical analysis;
  * draw a chart of generated or loaded real prices and save it in html-format (example: `./media/index.html`);
  * generate prices, a chart and some data on price behavior can be saved as a regular png-image (example: `./media/index.html.png`).

[![gift](https://badgen.net/badge/gift/donate/green)](https://yoomoney.ru/fundraise/BxB9DQNvJnk.230111)
