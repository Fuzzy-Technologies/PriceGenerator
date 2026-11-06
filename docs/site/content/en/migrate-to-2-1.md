# Migrate to PriceGenerator 2.1

[Русский](../ru/migrate-to-2-1.md) · [简体中文](../zh-CN/migrate-to-2-1.md)

| Version  | Role                                                                                  |
| -------- | ------------------------------------------------------------------------------------- |
| `1.4.93` | Historical PyPI release and starting point for 1.x migrations.                        |
| `v2.0.0` | GitHub test tag for the modern runtime at `83b1b75a99be06947a93314d6c2509a257ed6b3e`. |
| `2.1.0`  | GitHub pre-release with Monte Carlo, optional fuzzy diagnostics, and faster exports.  |

## Moving a 1.4.93 project

Keep the old environment, input files and outputs if you need to reproduce
1.x experiments. Set up a separate CPython 3.10–3.13 environment for the modern
package. Replace the mutable generator with `GenerationConfig` and
`Generate(config)`, or replace old CLI flags with the `generate` subcommand.
Convert existing files to canonical UTC OHLCV with the header
`datetime,open,high,low,close,volume` before calling `validate` or `chart`.
An old seed belongs to the old model. Capture a new manifest for the v2 fixture.
[Data contract](../../../data-contract.md) · [API and chart migration](../../../chart-migration.md)

## Moving a v2.0.0 test project

Keep its manifests and environment for exact reproduction of the test runs.
When evaluating 2.1, regenerate a fixture from the same configuration in a
clean installation and compare the OHLCV fingerprints. Check renderer outputs
separately. Core exports standalone SVG and offline interactive HTML.
Use `--no-view` for CLI automation or `view=False` from Python. PNG and JPEG
require the matching `export` extra. [Model assumptions and limits](../../../model-regime-v2.md)

## Check a seeded fixture

Install the 2.1 archive from the [GitHub pre-release](release-2-1.md),
then run the commands in a fresh output directory.

```sh
python -I -m pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 60 --output prices.csv --manifest scenario.json
python -I -m pricegenerator validate prices.csv --timeframe-seconds 60 --no-gaps
python -I -m pricegenerator replay scenario.json --output replay.csv
python -I -m pricegenerator chart prices.csv --output chart.html --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

Validation should report 240 valid rows. Under the recorded environment,
`prices.csv` and `replay.csv` match byte for byte. The
[animated CLI example](../../../examples/cli-demo.md) uses a separate 2.0.0
fixture. Its transcript records the command, export and reproduction steps.
