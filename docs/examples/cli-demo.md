# Generate, chart, and replay a scenario

![Animated terminal recording with a progressively revealed OHLCV candlestick chart](../assets/pricegenerator-cli-demo.gif)

The demo uses the installed [PriceGenerator v2.0.0 pre-release](https://github.com/Fuzzy-Technologies/PriceGenerator/releases/tag/v2.0.0) with the `export` extra. It creates 120 hourly OHLCV candles with seed 42, writes the manifest, exports the native PNG and checks the replayed CSV byte for byte. The status lines annotate verified files. The animation progressively reveals the actual exported candles and their volume bars.

## Commands

Run these from a writable directory with the package installed. The last command uses a POSIX shell.

```bash
pricegenerator generate --seed 42 \
  --horizon 120 --output prices.csv \
  --manifest scenario.json
pricegenerator chart prices.csv \
  --output chart.png --width 790 \
  --height 460 --no-view
pricegenerator replay scenario.json \
  --output replay.csv
cmp prices.csv replay.csv
```

## Regenerate the recording

Run the recorder with an isolated installation of the [v2.0.0 source tag](https://github.com/Fuzzy-Technologies/PriceGenerator/tree/v2.0.0), the tag's modern dependency constraints and Linux DejaVu Sans fonts in `/usr/share/fonts/truetype/dejavu`. It runs the installed CLI in a temporary directory and stops if replay changes the CSV bytes.

```bash
python -I tools/record_cli_demo.py docs/assets/pricegenerator-cli-demo.gif
```

The checked-in recording uses CPython 3.12, pandas 2.2.3, NumPy 2.2.6, Pillow 12.0.0 and resvg-py 0.5.0. The input and replay matched at SHA-256 `7dfc39216f109d1aaf74363e55450b1d9629332295bc2d5b00ca606c0d58b022` in this environment. Font and raster dependencies can change pixels on other systems.
