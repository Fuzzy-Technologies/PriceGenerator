---
layout: default
lang: zh-CN
route: scenario-guide
title: "K 线和成交量是怎样生成的？"
permalink: /zh-CN/scenario-guide/
redirect_from:
  - /docs/site/content/zh-CN/scenario-guide.html
---
# K 线和成交量是怎样生成的？
{: id="合成-ohlcv-场景及其适用范围" }

一根 K 线记录一个时段的开盘价、最高价、最低价和收盘价，图下的量柱对应同一时段的成交量。PriceGenerator 逐根计算这些数值，生成可供测试的分钟线或小时线。[画出第一张 K 线图](https://fuzzy-technologies.com/PriceGenerator/zh-CN/quick-start/)

## 先选一项要做的测试
{: id="选择一个用例" }

调试行情导入程序或核对指标时，可以一直使用同一份 CSV，这样每次修改代码都能对照前一次的结果。检验策略时，可以按同样的参数生成多段行情，交给自己的回测程序，分别比较交易记录和策略回撤。若要判断模拟行情像不像某个交易品种，就需要真实数据。[BTC/USD 实验](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#bitstamp)用一个月的历史行情估计参数，再用下一个月的数据检验。

## 五步生成一根 K 线
{: id="一根-k-线是怎样生成的" }

1. **确定开盘价。** 第一根 K 线从 `initial_price` 开始，默认值为 100。此后沿用上一根的收盘价。比如上一根收在 102，下一根就从 102 开盘。
2. **确定波动水平。** 每根 K 线开始时，模型决定维持当前波动状态，还是在低波动与高波动之间切换。高波动时，无论上涨还是下跌，价格波幅通常都更大。
3. **计算收盘价。** 将漂移项、随机波动和偶尔发生的价格跳变相加，得到这根 K 线的对数收益率，再从开盘价推算收盘价。如果越过设定的价格边界，模型在对数价格上将越界部分折回区间内。
4. **确定最高价和最低价。** 开盘价和收盘价定下实体的两端。模型分别抽取上影线和下影线的长度，得到这一时段的最高价和最低价。影线到达价格边界即止。
5. **计算成交量。** 从基础水平 `volume_base` 出发，模型考虑本次价格变动的幅度，并保留上一时段的部分随机波动。默认模型把结果取整，每根 K 线至少为 1。

旧版 1.4.93 先决定这根 K 线收涨还是收跌，再在允许范围内均匀抽取实体长度。指定一段上涨或下跌行情时，还可以改写最后的收盘价。成交量则在取决于上一根成交量的区间内抽取。2.2 改用收益率推算收盘价。设置正漂移会提高收益率的均值，但一根 K 线乃至整段行情仍有可能收跌。[1.4.93 源码](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v1.4.93/pricegenerator/PriceGenerator.py)

## 图上的 32 条模拟走势怎么看？
{: id="32-条路径能说明什么" }

让价格从 100 出发，保持参数不变，独立生成 32 段行情。取第 120 个小时的 32 个收盘价，从小到大排列。下面这个例子的中位数是 **101.27**，第 5 和第 95 百分位数分别是 **75.01** 和 **150.46**。这两个数给出该时刻中间约九成模拟结果的范围。

每个小时都重新做一次排序。共有 32 个价格时，中位数是排序后第 16 个和第 17 个价格的平均值。把各小时的三个统计值分别连起来，就得到图上的三条线。中位数线未必与任何一次模拟的走势重合。图上的 K 线和量柱则始终来自第一次模拟。一条路径可能在某个小时越过上下界。因此，观察某一小时的区间宽度，可以了解这组参数下走势在该时刻有多分散。

```sh
python -m pricegenerator monte-carlo --seed 42 --paths 32 --horizon 120 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --chart range.html --output range.json
```

用浏览器打开 `range.html` 即可查看结果。要用这些行情检验策略，可[按编号取出每一条价格路径](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#paths)，分别运行自己的回测程序。

## 导入行情需要哪些字段？
{: id="理解-k-线数据" }

CSV 表头为 `datetime,open,high,low,close,volume`。每根 K 线的开盘时间统一转换为纳秒精度的 UTC 时间，按时间顺序排列，不能重复。价格和成交量均用有限的 `float64` 数值表示，成交量不能为负。每根 K 线都应满足 `low <= min(open, close)` 和 `high >= max(open, close)`。外部数据允许零价和负价，内置模型生成的价格均为正数。

券商导出的时间若未注明时区，导入时请指定原始时区。校验时间间隔时要提供 K 线周期，休市造成的间隔应予保留。[CSV 格式说明](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#csv) · [如何向 MT5 导入分钟线](https://fuzzy-technologies.com/PriceGenerator/zh-CN/quick-start/#与-metatrader-5-交换-k-线)

## 模型如何计算价格和成交量
{: id="构建可控的合成场景" }

默认模型 `regime_v3` 从低波动状态开始。每生成一根 K 线，模型都有 `1 - regime_persistence` 的概率切换状态。在低波动状态下，收益率随机波动项的标准差为 `volatility`，在高波动状态下则为 `volatility × regime_scale`。参数以**一根 K 线**为单位。从分钟线切换到小时线时，需要另行设定适合小时行情的波动率。

考虑价格上下限之前，模型先计算对数收益率：

<i>r</i> = μ + σ · <i>Z</i> + σ₀ · <i>s</i> · <i>B</i> · <i>Z</i><sub>shock</sub>。

μ 是漂移项（`drift`），σ 是当前状态下的波动率，σ₀ 是基础波动率，<i>s</i> 是跳变幅度系数（`shock_scale`）。两个 <i>Z</i> 是彼此独立的标准正态随机变量，<i>B</i> 与两者独立，以 `shock_probability` 的概率取 1，否则为 0。只要没有越过边界，**收盘价就等于开盘价乘以 exp(<i>r</i>)**。价格折回边界以内时，最终的对数收益率会发生变化。影线也在对数价格上计算，上、下影线偶尔会加长，两侧各自独立。

成交量的计算使用**最终**的对数收益率。模型取其绝对值，除以当前状态下的波动率，衡量这次价格变动相对平常有多大。在随机扰动相同的情况下，价格变动越大，模拟成交量通常也越大，直至达到上限。`volume_return_coupling` 控制量价联系的强弱，`volume_persistence` 决定上一根 K 线的随机扰动会保留多少，`volume_ceiling` 规定成交量上限。

这里的整数表示模拟的交易活跃程度，并没有预设为股数、合约张数或 BTC 数量。实际成交量要以数据来源的单位为准，导入 CSV 时可以保留小数。需要复现采用连续成交量的旧实验时，可指定 `regime_v2`。[模型源码](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.2.1/pricegenerator/models.py) · [数值校验示例](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.2.1/tests/test_regime_v2_oracles.py)

## 查看图表，核对统计结果
{: id="检查结果并保留来源记录" }

在[快速入门](https://fuzzy-technologies.com/PriceGenerator/zh-CN/quick-start/)中保存了 `prices.csv` 的目录执行以下命令。

```sh
python -I -m pricegenerator analyze prices.csv --output statistics.json
python -I -m pricegenerator chart prices.csv --output analysis.html --analysis --no-view
```

打开 `analysis.html`。加上 `--analysis` 后，图中会出现 **Indicators**。选择 **Bollinger bands** 可叠加布林带，选择 **SMA 50 / 200** 可比较两条均线。第二条均线至少需要 200 根 K 线。整段行情的最高和最低收盘价、Zig-Zag 的历史转折点，都要等后面的数据出来才能确定。回测时若把它们当成当时已经知道的信号，就引入了未来数据。[图表与指标说明](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#charts)

![小时 K 线图上叠加了布林带和 50、200 小时均线，下方为模拟成交量。](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-chart-analysis.webp)

`statistics.json` 保存统计结果，某项指标无法计算时会给出原因。复现实验时请保留运行清单、命令、软件包和依赖版本。行情是否相同看 OHLCV 校验值，导出的图片是否完全相同则看文件本身的校验值。[统计指标说明](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#analysis)

## 还可以做哪些实验？
{: id="明确研究-api-的假设" }

Python 接口支持根据历史行情估计参数、分块重采样和自定义压力测试情景。CPython 3.13–3.15 还可以使用模糊诊断，分别将波动率和交易活跃程度与基准值比较，计算市场状态评分。评分独立于 K 线生成过程。[研究功能](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#research)

检验模型时，除了收益率的分布，还要看相邻时段之间的关系。模拟撮合或评估交易执行时，通常还需要点差、交易时段、订单簿或逐笔数据，具体取决于测试目标。[与历史行情对照](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#compare) · [如何检验模型](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#validation) · [Python API 手册](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#development)

[English](../en/scenario-guide.md) · [Русский](../ru/scenario-guide.md)
