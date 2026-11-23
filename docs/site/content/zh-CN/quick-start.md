---
layout: default
lang: zh-CN
route: quick-start
title: "生成第一份行情数据，画出 K 线图"
permalink: /zh-CN/quick-start/
redirect_from:
  - /docs/site/content/zh-CN/quick-start.html
---
# 生成第一份行情数据，画出 K 线图
{: id="复现合成-ohlcv-场景" }

下面用四个小时的分钟行情走一遍完整流程。先生成 240 根 K 线，保存为 CSV，再打开图表看看两条均线各从哪一分钟开始出现。最后还可以用同一组设置重新生成数据，核对两份文件是否完全一致。[K 线生成原理](https://fuzzy-technologies.com/PriceGenerator/zh-CN/scenario-guide/) · [2.2.1 版本说明](https://fuzzy-technologies.com/PriceGenerator/zh-CN/release-2-2/)

## 安装 PriceGenerator 2.2.1

[PyPI 上的 2.2.1](https://pypi.org/project/pricegenerator/2.2.1/) 支持 CPython 3.10–3.15。用已安装的 Python 创建虚拟环境。

```sh
python -m venv .venv
```

Windows PowerShell 用户运行 `.\.venv\Scripts\Activate.ps1` 激活环境。Linux 或 macOS 用户运行 `. .venv/bin/activate`。接着安装软件包。下面的版本检查应显示 `2.2.1`。

```sh
python -m pip install pricegenerator==2.2.1
python -m pip check
python -I -c "from importlib.metadata import version; print(version('pricegenerator'))"
mkdir pg-example
cd pg-example
```

## 生成 CSV 并查看图表
{: id="生成验证和绘图" }

```sh
python -I -m pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 60 --output prices.csv --manifest scenario.json
python -I -m pricegenerator validate prices.csv --timeframe-seconds 60 --no-gaps
python -I -m pricegenerator replay scenario.json --output replay.csv
python -I -m pricegenerator chart prices.csv --output chart.html --analysis --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

`prices.csv` 保存行情，`scenario.json` 记录生成参数、软件版本和运行环境，后文称为「运行清单」。执行 `validate` 后，应看到 240 行和 `"valid": true`。`fingerprint` 是这组 K 线数据的校验值，与清单中的同名字段一致。`replay` 会根据清单重新生成行情并核对结果。在同一环境中，两份 CSV 的内容逐字节相同。

用浏览器打开 **`chart.html`**。上方是价格，下方的柱状图显示每分钟的模拟成交量。滚动鼠标滚轮可以缩放。选择 **Box zoom** 后，拖出一个矩形即可放大该区域。**Export PNG** 保存当前可见的 K 线、成交量和已开启的指标。需要在报告中插图时，也可以使用 `chart.svg`。

**怎样显示均线？** 生成 HTML 时加上 `--analysis`，如上例所示。Python 中使用 `Chart(prices, "chart.html", analysis=True)`。打开图表，在 **Indicators** 中选择 **SMA 50 / 200**。50 周期均线从第 50 根 K 线开始有值，200 周期均线要到第 200 根才出现。选择 **Bollinger bands** 可查看布林带，**Midpoint** 会标出每根 K 线最高价和最低价的中点。图中还可查看 HMA、VWMA、PSAR、Alligator 和 Zig-Zag。展开 **Individual series** 可单独显示或隐藏一条线。点击 **Light theme** 可切换到浅色主题，**Detailed statistics** 中有完整的统计结果。

## 用 Python 生成同一份数据
{: id="用-python-生成相同的序列" }

在示例目录里将以下代码保存为 `scenario.py`，然后运行 `python -I scenario.py`。

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

WriteCSV(prices, "python-prices.csv", volume_as_count=True)
Chart(prices, "python-chart.svg", view=False)
Chart(prices, "python-analysis.html", analysis=True, view=False)
print(manifest["fingerprint"])
```

程序打印的校验值应与命令行示例一致。随机种子（`seed`）决定所用的随机数序列。要复现整份行情，还需要相同的模型、起始时间、K 线周期和其他参数。这些信息都保存在清单中。

## 怎样复现文档里的图？
{: id="记录图表来源" }

请随图保留运行清单、软件版本、绘图命令及参数。清单中的 OHLCV 校验值用来核对行情本身。如果还要逐字节核对图片，可另外记录图片文件的 SHA-256。字体和绘图软件版本都可能影响 PNG 或 JPEG 的内容。对于蒙特卡洛图，还需记录路径数、各路径的种子或种子生成规则，以及所用的分位数。

[指标示意图](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#charts)使用的是另一组数据。[绘图脚本](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.2.1/tools/chart_examples.py)在模拟行情中加入了休市时段和成交量为零的 K 线。从 `v2.2.1` 源码根目录运行 `python -m tools.chart_examples --output-dir pg-figures --html`，即可生成相应的 SVG、HTML 和参数说明。

## 与 MetaTrader 5 交换 K 线

CSV 使用 UTF-8 编码，表头为 `datetime,open,high,low,close,volume`。时间按 ISO 8601 记录，使用 UTC。字段以逗号分隔，小数点用英文句点。若券商导出的时间未注明时区，导入前请指定原始时区。保留休市造成的间隔。[CSV 格式说明](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#csv)

使用 `CustomRatesReplace` 导入时，请在 MT5 中新建自定义品种，并限定要替换的历史区间。按本例直接生成 1 分钟 K 线（M1），每根的开盘时间都应落在整分钟。MQL5 的 `datetime` 以自 1970 年起经过的秒数表示时间，转换前请检查日期范围和分钟对齐情况。

将价格舍入到该品种规定的小数位数后，再检查开盘价和收盘价是否都落在最低价与最高价之间。点差以点为单位另行指定。如果测试只需要一个代表报价活跃程度的数，可将模拟的整数成交量填入 `tick_volume`。`real_volume` 应取自实际成交记录。将带小数的资产数量写入整数字段前，先确定计量单位。[MqlRates 结构](https://www.mql5.com/zh/docs/constants/structures/mqlrates) · [datetime 类型](https://www.mql5.com/zh/docs/basis/types/integer/datetime)

导入后从终端导出几根 K 线，核对时间、价格和成交量。要使用基于真实报价的逐笔回测模式，还需要相应的历史逐笔数据。[CustomRatesReplace](https://www.mql5.com/zh/docs/customsymbols/customratesreplace) · [自定义品种的历史行情](https://www.mql5.com/zh/book/advanced/custom_symbols/custom_symbols_rates)

[English](../en/quick-start.md) · [Русский](../ru/quick-start.md)
