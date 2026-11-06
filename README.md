# PriceGenerator

![PriceGenerator by Fuzzy Technologies. Synthetic market data generator.](https://raw.githubusercontent.com/Fuzzy-Technologies/PriceGenerator/develop/docs/assets/pricegenerator-product-card.webp)

[English guide](docs/site/content/en/scenario-guide.md) ·
[Русский](docs/site/content/ru/scenario-guide.md) ·
[简体中文](docs/site/content/zh-CN/scenario-guide.md) ·
[What's new in 2.1](docs/site/content/en/release-2-1.md)

Reproducible synthetic OHLCV scenarios for trading-system tests and quantitative
research. The v2 API separates generation, validation, diagnostics, CSV, replay
and charts. It produces synthetic test data; it does not forecast markets or
establish that a strategy is profitable.

## Install

CPython 3.10–3.13 is supported. PyPI currently provides the historical 1.4.93
release. The [2.1 GitHub pre-release](docs/site/content/en/release-2-1.md)
and the [2.0.0 test release](https://github.com/Fuzzy-Technologies/PriceGenerator/releases/tag/v2.0.0)
provide the v2 APIs below. Install from the 2.1 source archive or checkout:

```bash
python -m pip install .
python -m pip install '.[export]'  # Optional PNG/JPEG.
```

The first modern PyPI release is planned for 2.2.0. See the
[release runbook](docs/releasing.md) for verification and publishing.

## Generate and save

```python
from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV

config = GenerationConfig(seed=0, horizon=240, volatility=0.01)
prices = Generate(config)
WriteCSV(prices, "prices.csv")
restored = ReadCSV("prices.csv")
```

`GenerationConfig` is immutable. Defaults include a fixed UTC start and the
versioned `regime_v2` model; seed zero is valid. Generation owns a private RNG
and leaves process-global random state alone. See [model semantics](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/model-regime-v2.md)
for drift, regimes, independent shocks/wicks, volume, reflection and bounds.

Canonical data has exactly `datetime, open, high, low, close, volume`: UTC
nanosecond timestamps and finite float64 values. Imported naive timestamps need
an explicit timezone. `ValidateOHLCV` returns detached canonical data and can
check cadence/gaps. Structural validity is separate from empirical market fit.

## Replay, diagnose and chart

```python
import json
from pricegenerator import Analyze, Chart, CreateManifest, Indicators, Replay

manifest = CreateManifest(config, prices)
with open("scenario.json", "w", encoding="utf-8") as stream:
    json.dump(manifest, stream, allow_nan=False, indent=2)
replayed = Replay(manifest)
statistics = Analyze(prices).ToDict()
indicators = Indicators(prices).ToDict()
chart_path = Chart(prices, "chart.html", view=False)
```

A manifest records full configuration, model/RNG/library identity, environment
and separate scenario-identity and canonical-output fingerprints. Replay requires
a matching environment by default; `strict_environment=False` still requires exact fingerprint equality.
Diagnostics and indicators do not mutate source data. Missing/domain-limited
estimates include reasons, rather than fabricated finite values.

`Chart(prices)` creates offline interactive HTML and opens it in the browser.
Use `view=False` in batch jobs. SVG needs an explicit `.svg` destination; PNG and
JPEG additionally need `[export]`. `analysis=True` explicitly attaches financial
overlays and diagnostics. `DisplayChart(prices)` embeds HTML in a notebook;
install `.[notebook]` if the host lacks notebook tooling. Charts contain one
translucent corporate wordmark in the price panel. See [chart guide](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/chart-migration.md).

## Command line

```bash
pricegenerator generate --seed 0 --horizon 240 --output prices.csv --manifest scenario.json
pricegenerator replay scenario.json --output replay.csv
pricegenerator validate prices.csv --timeframe-seconds 3600 --no-gaps
pricegenerator analyze prices.csv --output statistics.json
pricegenerator chart prices.csv --output chart.html --no-view --analysis
```

Version 2.1 also provides [ensemble generation and exact
replay](docs/monte-carlo.md) through the CLI and Python, and optional
[fuzzy regime diagnostics](docs/fuzzy-diagnostics.md) on Python 3.13.

`python -m pricegenerator` exposes the same commands. A JSON `--config` supplies
all generation parameters; explicit common CLI flags override those fields.
Unknown fields, nonfinite values, ambiguous times and aliased input/output paths
fail early. The old mutable class, rendering methods and old CLI flags are
removed; [migration](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/chart-migration.md) and [ADR-0010](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/adr/0010-modern-only-public-api.md)
record the deliberate break. Historical evidence remains [archived](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/baseline/README.md).

## Run a complete experiment

In 2.2, [compare two OHLCV CSVs](docs/reference-comparison.md) at an explicit
bar interval, or use the [experiment bundle](docs/examples/experiment-bundle.md)
to generate two seeded fixtures. The example verifies single-path and ensemble
replay and records a comparison, an offline quantile chart and checksums.

## Develop and extend

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
```

Start with [development commands](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/development.md), [packaging](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/packaging.md)
and the [ADRs](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/adr/README.md). **AI contributors: read [AGENTS.md](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/AGENTS.md)
before changing code**, then follow the linked protocol and style contract.
Research helpers remain experimental and module-qualified under
`pricegenerator.calibration`, `pricegenerator.evaluation`,
`pricegenerator.extended_models` and `pricegenerator.registry`; they are outside
the compact root API and do not imply validation against every real market.
Large-data adapters are `GenerateChunks` and `WriteCSVChunks`.

[Repository](https://github.com/Fuzzy-Technologies/PriceGenerator) ·
[Issues](https://github.com/Fuzzy-Technologies/PriceGenerator/issues) ·
[Apache-2.0 license](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/LICENSE) · [Русский](README_RU.md)
