---
layout: default
lang: zh-CN
route: experiments
title: "合成行情实验"
permalink: /zh-CN/experiments/
redirect_from:
  - /docs/site/content/zh-CN/experiments.html
---
# 合成行情实验

## 在相同条件下模拟 32 次
{: #monte-carlo }

固定初始价格和模型参数，为每条路径使用各自可复现的随机序列。`quantiles.html` 中的 K 线和成交量取自第一条路径。三条曲线分别表示每个小时所有收盘价的第 5、第 50 和第 95 百分位数。在这个 120 小时的实例中，最后一个小时的三个数为 75.01、101.27 和 150.46。单条路径在其他时点可能穿过边界。

```sh
python -m pricegenerator monte-carlo --seed 42 --paths 32 --horizon 120 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --output ensemble.json --manifest ensemble-manifest.json --chart quantiles.html
python -m pricegenerator replay-ensemble ensemble-manifest.json --output replayed.json
```

JSON 列出每条路径的最大价格回撤。要检验入场、出场和交易成本，请逐条生成行情，在自己的回测程序中运行策略。

```python
from dataclasses import replace
from datetime import datetime, timezone
from pricegenerator import Generate, GenerationConfig
from pricegenerator.monte_carlo import DerivePathSeed

config = GenerationConfig(seed=42, horizon=120, start=datetime(2025, 1, 6, tzinfo=timezone.utc))
for index in range(32):
    candles = Generate(replace(config, seed=DerivePathSeed(config.seed, index)))
    print(index, round(candles["close"].iloc[-1], 2))
```

## 对照模拟与实测数据
{: #compare }

准备两份标准 OHLCV CSV，选择没有缺口的连续区间，两份数据应采用同一周期和可比的成交量单位。可用 `--tolerances` 传入以指标名为键的绝对容差 JSON。命令成功说明比较已经完成，是否在容差内应查看报告的逐项结果。

```sh
python -m pricegenerator compare observed.csv synthetic.csv --timeframe-seconds 3600 --output comparison.json
```

## 这些数据像哪个市场？
{: #bitstamp }

默认场景从 100 起步，没有指定交易品种。要复现真实市场的某些特征，可以先选择品种和周期，在较早的一段历史数据上估计参数，再用后续数据检验。在 Bitstamp BTC/USD 小时线实验中，使用 2024 年 9 月的 720 根 K 线拟合，再用 10 月的 744 根检验。16 次模拟的收益率波动和 BTC 小时平均成交量都落入预设容差。

受限的 `regime_v2` 拟合得到恒定的每小时 71.93 BTC。实际市场均值为 67.45 BTC，成交量与收益率绝对值的相关系数为 0.522。成交量恒定时该系数无定义。模拟与实测数据中波动聚集的程度也不同。这个例子说明可以复现选定的市场统计特征，并测量哪些性质仍有差异。默认 `regime_v3` 生成随时间变化的整数活动量。[数值结果与数据来源](https://fuzzy-technologies.com/PriceGenerator/docs/evidence/reference-bitstamp-holdout.json)。

## 分享完整实验
{: #bundle }

在与已安装软件包版本相同的源码根目录中运行示例，输出目录须为新目录。它将生成两份合成小时线 CSV、运行清单、比较报告、包含 32 条路径分位数的图表及文件校验和。第二条命令校验已保存的文件。

```sh
python -I tools/experiment_bundle.py create pg-experiment
python -I tools/experiment_bundle.py verify pg-experiment
```

打开 `pg-experiment/quantiles.html`。要查看指标，运行 `python -m pricegenerator chart pg-experiment/scenario.csv --analysis --output analysis.html --view`。实验包只有 120 根 K 线，若要显示 200 周期均线，可使用[快速入门](https://fuzzy-technologies.com/PriceGenerator/zh-CN/quick-start/)的 240 根 K 线。

[English](../en/experiments.md) · [Русский](../ru/experiments.md)
