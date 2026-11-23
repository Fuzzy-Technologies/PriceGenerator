---
layout: default
lang: zh-CN
route: release-2-2
title: "PriceGenerator 2.2.1"
permalink: /zh-CN/release-2-2/
redirect_from:
  - /docs/release-2-2-zh-CN.html
---
# PriceGenerator 2.2.1

[PyPI 上的 2.2.1 发行版](https://pypi.org/project/pricegenerator/2.2.1/)

2.2.1 提供统一风格的中、英、俄三语网站，并修复软件包描述中的文档链接。以下示例使用 2.2 系列的 K 线模型。

PriceGenerator 为交易系统测试生成可复现的合成 K 线。2.2 可以比较两份同周期
的 OHLCV 数据，查看波动率、回撤和成交量等指标的差异。你也可以把配置、数据、
对比结果和图表一起交给同事，让对方复现整个实验。

- **对比两份数据。** 指定 K 线周期，并按需为各项统计指标设置容差。
- **分享实验。** 保存种子和清单，复现单条价格轨迹或整组蒙特卡洛模拟。
- **查看不同模拟结果。** 蜡烛和成交量来自一次模拟，三条分位数曲线汇总同一时刻
  32 次模拟的收盘价。

![一条模拟价格轨迹及 32 次模拟的分位数](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-2-2-experiment-quantiles.svg)

在最后一个小时，将 32 个收盘价排列后，中位数为 **101.27**，第 5 和第 95 百分位数分别为 **75.01** 和 **150.46**。每个小时独立计算，一条路径可以穿过边界。

默认生成整数形式的合成活跃度计数。导入的资产成交量保留原有精度。

## 试用交互图表

安装 PriceGenerator 2.2.1 后，生成 240 根小时 K 线，然后用浏览器打开本地 HTML。

```sh
python -m pip install pricegenerator==2.2.1
pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --output candles.csv
pricegenerator chart candles.csv --output candles.html --analysis --no-view
```

**如何显示指标按钮？** 用同一份 CSV 重新生成 HTML，并加上 `--analysis`。
在 Python 中可以调用 `Chart(prices, "chart.html", analysis=True)`。
用浏览器打开文件后，点击 **Bollinger bands** 查看均线周围的波动范围，
点击 **SMA 50 / 200** 比较两条均线，或点击 **Midpoint** 标出每根 K 线
最高价与最低价的中点。还可以切换 HMA、VWMA、PSAR、Alligator 和 Zig-Zag。
展开 **Individual series** 可以单独开关一条曲线。SMA 200 至少需要 200 根 K 线。

用滚轮或 **Box zoom** 放大选定区间。**Light theme** 切换至浅色主题，
**Export PNG** 保存当前视图。图表下方显示简要概览，展开
**Detailed statistics** 可查看完整报告。

![离线 K 线和成交量图，已开启布林带及 50 和 200 周期均线](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-chart-analysis.webp)

[快速入门](https://fuzzy-technologies.com/PriceGenerator/zh-CN/quick-start/) · [完整实验](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#bundle)

[English](https://fuzzy-technologies.com/PriceGenerator/en/release-2-2/) · [Русский](https://fuzzy-technologies.com/PriceGenerator/ru/release-2-2/)
