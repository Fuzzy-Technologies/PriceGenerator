# 复现合成 OHLCV 场景

[English](../en/quick-start.md) · [Русский](../ru/quick-start.md)

使用固定随机种子生成行情序列，根据场景清单复现数据，并在不启动浏览器的情况下
生成图表。该序列可用于软件测试和受控实验。时间戳为合成数据，价格变化取决于
所配置的模型参数。

## 从经过验证的源码标签安装

使用 CPython 3.10–3.13 和独立环境。本示例使用 GitHub 测试标签 `v2.0.0`，
对应提交 `83b1b75a99be06947a93314d6c2509a257ed6b3e`。

```sh
git clone --branch v2.0.0 --depth 1 https://github.com/Fuzzy-Technologies/PriceGenerator.git pg-demo
cd pg-demo
git rev-parse HEAD
python -m venv .venv
```

在 POSIX Shell 中执行 `. .venv/bin/activate`，或在 Windows PowerShell 中
执行 `.\.venv\Scripts\Activate.ps1`。在源码目录中按约束安装依赖和软件包。
版本检查应输出 `2.0.0`。

```sh
python -m pip install -c requirements/modern.txt .
python -m pip check
python -I -c "from importlib.metadata import version; print(version('pricegenerator'))"
mkdir pg-example
cd pg-example
```

## 生成、验证和绘图

```sh
python -I -m pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 60 --output prices.csv --manifest scenario.json
python -I -m pricegenerator validate prices.csv --timeframe-seconds 60 --no-gaps
python -I -m pricegenerator replay scenario.json --output replay.csv
python -I -m pricegenerator chart prices.csv --output chart.html --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

验证结果会报告行数为 240、`"valid": true` 和规范 OHLCV 数据指纹。该指纹与
`scenario.json` 中的 `fingerprint` 一致。复现时会核对记录的配置、软件包版本、
运行环境和数据指纹。生成和复现的 CSV 内容相同。打开本地 `chart.html` 可以
缩放并查看数据，`chart.svg` 则是静态矢量图。

## 用 Python 生成相同的序列

在示例目录中将以下代码保存为 `scenario.py`，运行 `python -I scenario.py`。

```python
"""Reproduce a seeded minute-bar fixture using the installed package."""

from datetime import datetime, timezone

from pricegenerator import Chart, CreateManifest, Fingerprint, Generate, GenerationConfig, Replay, WriteCSV

config = GenerationConfig(
    seed=42,
    horizon=240,
    start=datetime(2025, 1, 6, tzinfo=timezone.utc),
    timeframe_seconds=60,
)
prices = Generate(config)
manifest = CreateManifest(config, prices)

if Fingerprint(Replay(manifest)) != Fingerprint(prices):
    raise RuntimeError("Replay changed the canonical OHLCV fingerprint")

WriteCSV(prices, "python-prices.csv")
Chart(prices, "python-chart.svg", view=False)
print(manifest["fingerprint"])
```

在相同环境下，输出的数据指纹与 CLI 示例一致。随机种子确定随机数流，
完整配置还规定模型、开始时间、周期及其他参数。请保存场景清单以便复现。

## 记录图表来源

请随图表保留源码标签或提交、生成清单、绘图命令及参数。将导出文件的 SHA-256
与 OHLCV 数据指纹分别记录。渲染器版本和字体可能影响位图结果。对于多路径
图表，还需记录各条路径的种子或种子派生规则、路径数量及汇总方法。

仓库中的行情和指标插图使用另一组测试数据。脚本先用固定种子生成序列，然后
显式加入交易时段间隔和零成交量 K 线。在该标签的仓库根目录运行
`python -m tools.chart_examples --output-dir pg-figures --html`，重新生成 SVG、
HTML 和来源说明。
[绘图脚本](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/tools/chart_examples.py) · [行情图说明](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/examples/modern-market.md)

## 与 MetaTrader 5 交换 K 线

PriceGenerator 写入 UTF-8 逗号分隔文件，表头为
`datetime,open,high,low,close,volume`，时间戳采用 ISO 8601 UTC，有限数值使用
小数点。从经纪商导入数据时，请先显式转换格式，并为无时区信息的时间戳指定
源时区。保留交易时段间隔，并按已知周期验证。
[规范 OHLCV 与 CSV 约定](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/data-contract.md)

通过 `CustomRatesReplace` 将数据导入 MT5 自定义品种时，适配器需要开盘时间
对齐至 M1 的分钟 K 线。可按上例直接生成 M1。MQL5 的 `datetime` 使用从
1970 年起算的整秒。转换前应检查范围及对齐。请明确如何把浮点 `volume` 映射
到整数 `tick_volume` 和 `real_volume`，以及如何设置以点为单位的点差。
记录按品种小数位数进行价格舍入的规则，转换后检查 OHLC 关系。使用单独的自定义
品种，并限定历史替换区间。
[CustomRatesReplace](https://www.mql5.com/en/docs/customsymbols/customratesreplace) · [MqlRates](https://www.mql5.com/en/docs/constants/structures/mqlrates) · [MQL5 datetime](https://www.mql5.com/en/docs/basis/types/integer/datetime)

本示例验证 Python 端的 CSV。终端导入、K 线往返校验和策略测试器设置需要
单独做集成验证。真实逐笔模式需要独立的逐笔历史数据。
[MQL5 自定义品种历史指南](https://www.mql5.com/en/book/advanced/custom_symbols/custom_symbols_rates)
