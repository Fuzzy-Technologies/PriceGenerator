---
layout: default
lang: zh-CN
route: reference
title: "行情数据与图表使用手册"
permalink: /zh-CN/reference/
redirect_from:
  - /docs/site/content/zh-CN/reference.html
---
# 行情数据与图表使用手册
{: id="k-线数据使用手册" }

## CSV 字段与成交量单位
{: #csv }

文件第一行是 `datetime,open,high,low,close,volume`，此后每行对应一根 K 线。开盘时间统一使用 UTC，按时间先后排列，不能重复。如果券商导出的时间没有注明时区，请在校验时用 `validate --timezone` 指定原始时区。开盘价和收盘价都应在最低价与最高价之间。对于连续交易的小时行情，可以用 `--timeframe-seconds 3600 --no-gaps` 检查有没有漏掉某个小时。

默认模型的 `volume` 是整数，表示这根 K 线所对应时段的模拟交易活跃程度。导入真实行情时，成交量的含义取决于数据来源，例如股票的股数、合约的张数或以 BTC 计量的成交数量。导入时会保留小数。在 Python 中调用 `WriteCSV(candles, "candles.csv", volume_as_count=True)`，可以像命令行一样把模拟生成的整数成交量写入 CSV。

## 查看图表和技术指标
{: #charts }

```sh
python -m pricegenerator chart candles.csv --analysis --output chart.html --view
```

基础图表显示 K 线和成交量。生成图表时加上 **`--analysis`**，即可使用指标面板并查看详细统计。在 **Indicators** 中选择 **SMA 50 / 200**，可以叠加按收盘价计算的两条简单移动平均线。200 周期均线要等第 200 根 K 线收盘才有第一个值。**Bollinger bands** 显示布林带，**Midpoint** 标出每根 K 线的最高价与最低价的中点，即 `(high + low) / 2`。

**Close limits and trends** 显示整段行情的最高和最低收盘价，以及连接首尾收盘价的直线。**Zig-Zag** 标出经后续价格走势确认的转折点。这些标记适合事后看图。用它们回测时，要考虑交易当时能否看到产生该标记所需的数据。

滚动鼠标滚轮或选择 **Box zoom** 可放大图表。**Export PNG** 将可见区间的 K 线、量柱及已开启的指标保存成图片。基础包支持离线 HTML 和 SVG。从命令行或 Python 直接生成 PNG、JPEG 时，还需安装 `pricegenerator[export]`。静态导出时加上 `--analysis`，图下还会附上完整统计报告。

## 收益率与回撤
{: #analysis }

`python -m pricegenerator analyze candles.csv --output stats.json` 会统计收益率、成交量、上涨和下跌的 K 线数量、分布特征以及观测值之间的相关性。按收盘价计算的**价格回撤**，指当前收盘价相对于此前收盘高点的跌幅。例如，前期最高收盘价为 100，随后收在 80，价格回撤就是 20%。若要计算策略账户的回撤，还需考虑持仓、成交和交易费用。某项指标无法计算时，报告会注明原因。

## 设置模型参数
{: #model }

漂移项和波动率均按单根 K 线设置。把时间间隔从 1 分钟改为 1 小时，只会改变时间戳的间距。要模拟小时行情，还需要为该周期选择合适的参数。交易日历、买卖价差、K 线内部的逐笔行情和订单撮合须另行处理。[K 线和成交量的生成原理](https://fuzzy-technologies.com/PriceGenerator/zh-CN/scenario-guide/)

## 参数估计与市场状态诊断
{: #research }

Python 接口支持用一段历史行情估计参数，然后用另一段行情检验。[Bitstamp 实验](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#bitstamp)估计了漂移、波动率和平均成交量。在所选设置下，每根模拟小时线的成交量都等于拟合期的小时均值。CPython 3.13–3.15 还支持可选的模糊诊断，通过比较波动率、活跃程度及其基准值，给出市场状态评分。这个评分不会改变生成的 K 线。

## 查阅 Python API
{: #development }

[PriceGenerator 2.2.1 Python API 参考手册](https://fuzzy-technologies.com/PriceGenerator/api/2.2.1/zh-cn/)按主题介绍函数、类、参数及返回结果，涉及价格、收益率或成交量时也说明计算口径。例如，[RunEnsemble](https://fuzzy-technologies.com/PriceGenerator/api/2.2.1/zh-cn/monte-carlo/#monte_carlo.RunEnsemble) 介绍如何汇总多条模拟路径上同一时刻的收盘价。旧版脚本可参阅[从 1.4.93 迁移](https://fuzzy-technologies.com/PriceGenerator/zh-CN/migration/)。

## 如何检验模拟结果
{: #validation }

先明确测试中最重要的行情特征。例如，一套依赖突然放量的策略，需要检查放量出现的频率，以及放量时价格如何变化。仅比较平均成交量会漏掉这两个问题。在较早的历史数据上选定允许的偏差，再用后续数据做样本外检验，并保留随机种子、运行清单和 K 线校验值，方便复核。

## 安装发行版
{: #packaging }

[PyPI](https://pypi.org/project/pricegenerator/2.2.1/) 提供 wheel 和源码包，两种发行包都会在干净环境中测试安装。运行 `python -m pip install pricegenerator==2.2.1` 即可安装示例使用的版本。需要直接导出 PNG 或 JPEG 时，运行 `python -m pip install "pricegenerator[export]==2.2.1"`。

[English](../en/reference.md) · [Русский](../ru/reference.md)
