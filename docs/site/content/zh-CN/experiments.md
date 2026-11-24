---
layout: default
lang: zh-CN
route: experiments
title: "用模拟行情做实验"
permalink: /zh-CN/experiments/
redirect_from:
  - /docs/site/content/zh-CN/experiments.html
---
# 用模拟行情做实验
{: id="合成行情实验" }

## 同样的参数，价格能走出多少种走势？
{: #monte-carlo }

只用一段行情做回测，很难判断策略是否恰好遇到了有利的走势。蒙特卡洛模拟的做法是保持假设不变，反复抽取随机数，让价格走出许多条不同的路径。下面这 32 次模拟使用相同的起始价、波动参数和时长，各次的随机波动不同。

```sh
python -m pricegenerator monte-carlo --seed 42 --paths 32 --horizon 120 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --output ensemble.json --manifest ensemble-manifest.json --chart quantiles.html
python -m pricegenerator replay-ensemble ensemble-manifest.json --output replayed.json
```

用浏览器打开 **`quantiles.html`**。K 线和量柱来自第一条路径。计算三条曲线时，每个小时都取**全部 32 条路径**的收盘价，将这些价格排序，取第 5 百分位数、中位数和第 95 百分位数。在最后一小时（第 120 小时），中位数为 **101.27**，中间约九成结果落在 **75.01 至 150.46** 之间。每个小时都单独排序，取第 16 个和第 17 个价格的平均值作为中位数。把这些中位数连在一起，得到的是一条统计曲线。单条路径也可能越过区间边界。

`ensemble.json` 记录了每条路径按收盘价计算的最大**价格回撤**。要计算**策略回撤**，请将各组 K 线分别送入自己的回测程序，并考虑持仓、成交价和交易成本。

### 其余 31 条路径在哪里？
{: #paths }

32 组行情都会完整生成。默认图上的 K 线和量柱来自**编号 00 的路径**，三条分位数曲线则用到了全部路径的收盘价。JSON 报告保留分位数、各条路径的最大价格回撤和复现行情所需的参数。每条路径的 CSV 需要单独导出。

下图用 K 线和成交量柱展示 00 号路径。其余 31 条路径各用一条灰色细线表示，沿线可以看到这条路径逐小时的收盘价。蓝线、紫线和金线分别表示第 5 百分位数、中位数和第 95 百分位数，每个小时都用该时刻的 32 个收盘价重新计算。

[![00 号路径的小时 K 线和成交量柱、其余 31 条路径的灰色收盘价曲线，以及三条彩色分位数线。](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.svg)](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.svg)

**[下载全部 32 份 CSV（ZIP）](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.zip)**。文件按 `path-00.csv` 到 `path-31.csv` 编号，每份有 120 根小时 K 线，包含开盘价、最高价、最低价、收盘价和成交量。

要导出自己的模拟结果，请在上一条命令生成 `ensemble.json` 的目录里运行下列 Python 代码。它读取本次实验的参数，根据路径编号还原各自的随机种子，并将 CSV 写入 `paths` 目录。路径编号从 0 开始。

```python
import json
from dataclasses import replace
from pathlib import Path

from pricegenerator import Generate, GenerationConfig, WriteCSV
from pricegenerator.monte_carlo import DerivePathSeed

report = json.loads(Path("ensemble.json").read_text(encoding="utf-8"))
config = GenerationConfig.FromDict(report["configuration"])
output = Path("paths")
output.mkdir(exist_ok=True)

for index in range(report["path_count"]):
    seed = DerivePathSeed(config.seed, index)
    candles = Generate(replace(config, seed=seed))
    WriteCSV(candles, output / f"path-{index:02d}.csv", volume_as_count=config.model == "regime_v3")
```

例如，要逐根查看 17 号路径的 K 线和成交量，可运行以下命令。

```sh
python -m pricegenerator chart paths/path-17.csv --analysis --output path-17.html --view
```

## 模拟行情与历史行情差多少？
{: #compare }

各准备一份 CSV，分别存放历史行情和模拟行情。选择无缺口的连续时段，确认两份数据的 K 线周期相同、成交量单位可比。例如，以 BTC 计量的成交量应与同样以 BTC 计量的数据比较。

```sh
python -m pricegenerator compare observed.csv synthetic.csv --timeframe-seconds 3600 --output comparison.json
```

`comparison.json` 列出两组数据各自的波动率、最大价格回撤、平均成交量等指标。可以事先为关心的指标设定允许的绝对偏差，将其写入 JSON 文件后用 `--tolerances` 指定。即使某项偏差超出允许范围，命令也能正常完成。要判断每一项是否合格，请查看报告里的 `within_tolerance`。

## BTC/USD 实例：均值接近，小时成交量走势却不同
{: #bitstamp }

默认场景从 100 起步，没有对应的交易品种。为了检验模型能否反映某个市场的特征，我们取了 Bitstamp 的 BTC/USD 小时行情，用 **2024 年 9 月的 720 根小时 K 线**估计 `regime_v2` 的参数，把 **10 月的 744 根**留作样本外检验。16 次模拟的小时收益率波动率和每小时平均成交量都在事先用 9 月数据设定的容许范围内。

但是，两组数据的成交量随时间变化的方式截然不同。这组参数生成的成交量**每个小时都是 71.93 BTC**。10 月实际成交量平均为每小时 67.45 BTC，各小时有高有低。成交量与小时收益率绝对值的相关系数为 **0.522**。模拟成交量恒定，这个相关系数没有定义。若策略依赖突然放量，这组模拟行情里就没有这样的信号。

相邻小时的波动也有差异。实际行情中，小时收益率平方的一阶自相关系数为 0.3345。在 16 次模拟中，这一指标的第 95 百分位数也只有 0.0395。

恒定成交量是本次参数估计方式带来的结果。平常使用默认的 `regime_v3` 时，模拟成交量为随时间变化的整数，用来表示交易活跃程度。[数据来源及各次模拟结果（JSON）](https://fuzzy-technologies.com/PriceGenerator/docs/evidence/reference-bitstamp-holdout.json)

## 把整个实验交给同事复查
{: #bundle }

在与已安装软件包版本相同的源码根目录中运行以下命令。`pg-experiment` 须为新目录。

```sh
python -I tools/experiment_bundle.py create pg-experiment
python -I tools/experiment_bundle.py verify pg-experiment
```

第一条命令生成两份模拟小时行情、各自的运行清单、对比报告、32 条路径的分位数图，以及文件校验值。第二条命令核对目录内容。将整个目录交给同事，就可以复查这次实验。

打开 `pg-experiment/quantiles.html` 查看价格分布。要查看技术指标，运行 `python -m pricegenerator chart pg-experiment/scenario.csv --analysis --output analysis.html --view`。本例只有 120 根 K 线。要画出 200 周期均线，请使用[快速入门](https://fuzzy-technologies.com/PriceGenerator/zh-CN/quick-start/)中的 240 根 K 线。

## 生成 100 万根 K 线需要多久？
{: #performance }

在搭载 AMD EPYC 9V74 的 Linux 服务器上，单个 Python 进程生成 **100 万根 1 分钟 K 线用时 3.72 秒**，约合**每秒 26.9 万根**。从开始生成到写完本地 CSV 共用 **8.59 秒**，文件大小为 109.5 MB。每根 K 线都有时间、四个价格和整数形式的模拟成交量。

| 1 分钟 K 线数量 | 在内存中生成 | 写入 CSV | 从开始生成到写完文件 |
| --------------: | -----------: | -------: | -------------------: |
| 10 万根         | 0.33 秒      | 0.45 秒  | 0.77 秒              |
| 100 万根        | 3.72 秒      | 4.87 秒  | 8.59 秒              |

两种数据量各测五次，每次启动一个新的 Python 进程，每列分别取中位数。测试使用 PyPI 发行版 2.2.1、CPython 3.14.10、pandas 2.3.3、NumPy 2.3.5，随机种子为 42。计时覆盖 `Generate` 和 `WriteCSV`，包括这两个接口的数据校验和本地缓冲写入。模块导入和预热在计时前完成，文件校验值在写入后计算，本次未绘图。实际速度取决于处理器和存储设备。

单条行情最多可生成 **100 万根 K 线**。一次蒙特卡洛模拟支持 2 至 10,000 条路径，**所有路径合计最多 100 万根 K 线**。例如，选择 32 条路径时，每条最多 31,250 根。要在自己的机器上复测，下载脚本，在已安装 2.2.1 的环境中运行 `python -I measure_generation.py 1000000`。[测试脚本](https://fuzzy-technologies.com/PriceGenerator/docs/evidence/measure_generation.py) · [各次用时及 CSV 校验值（JSON）](https://fuzzy-technologies.com/PriceGenerator/docs/evidence/generation-speed-2.2.1.json)

[English](../en/experiments.md) · [Русский](../ru/experiments.md)
