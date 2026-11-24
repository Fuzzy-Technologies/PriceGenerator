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

PriceGenerator 可以生成 K 线行情和成交量，用来测试交易软件。2.2 加入了行情对比功能：取一份历史行情和一份模拟行情，就能量化两者的差异。发现问题时，把参数、CSV 和图表交给同事，对方就能复现同一次实验。[从 PyPI 安装 2.2.1](https://pypi.org/project/pricegenerator/2.2.1/)

## 从 2.1 升级后能做什么？

- **对照真实行情。** 用 `compare` 比较两份相同 K 线周期的 CSV，查看波动率、价格回撤和成交量等指标相差多少。可以事先为关心的指标设定容许偏差。
- **分享可复现的实验。** 随附的示例把两组模拟行情、生成参数、对比报告和蒙特卡洛图保存在同一目录。交给同事后，可以用一条命令核对文件。[运行完整示例](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#bundle)
- **默认成交量改为整数。** 模拟数据用整数表示该时段的交易活跃程度。导入真实行情时仍保留原有单位和小数，例如以 BTC 计量的成交量。

## 蒙特卡洛图怎么看？

图中的 K 线和成交量柱来自第一条模拟路径，其余 31 条路径的小时收盘价用灰色细线表示。想看某一小时的价格分布，可以比较三条彩色曲线在这一刻对应的价格。

[![00 号路径的小时 K 线和成交量柱、其余 31 条路径的灰色收盘价曲线，以及三条彩色分位数线。](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.svg)](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.svg)

以最后一小时为例，紫线为 **101.27**，是该小时 32 个收盘价的中位数。蓝线 **75.01** 和黄线 **150.46** 分别是第 5 和第 95 百分位数。其他小时各自重新计算，曲线间距反映的是这一时刻模拟价格的分散程度。[如何取出每条路径的行情数据](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#paths)

## 画一张自己的 K 线图
{: id="试用交互图表" }

用下面的命令生成 240 根小时 K 线，再用浏览器打开 `candles.html`，离线也能查看。

```sh
python -m pip install pricegenerator==2.2.1
pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --output candles.csv
pricegenerator chart candles.csv --output candles.html --analysis --no-view
```

加上 **`--analysis`** 就能开启指标面板。选择 **Bollinger bands** 查看布林带，或者用 **SMA 50 / 200** 叠加 50 小时和 200 小时均线。Python 中对应的写法是 `Chart(prices, "chart.html", analysis=True)`。用 **Box zoom** 框选感兴趣的区间，再点击 **Export PNG** 保存该区间的图像。[图表操作说明](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#charts)

![小时 K 线图叠加布林带和两条均线，下方为同一时段的成交量。](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-chart-analysis.webp)

[快速入门](https://fuzzy-technologies.com/PriceGenerator/zh-CN/quick-start/) · [比较两份 CSV](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#compare) · [Python API 参考手册](https://fuzzy-technologies.com/PriceGenerator/api/2.2.1/zh-cn/) · [迁移 1.4.93 脚本](https://fuzzy-technologies.com/PriceGenerator/zh-CN/migration/)

[English](https://fuzzy-technologies.com/PriceGenerator/en/release-2-2/) · [Русский](https://fuzzy-technologies.com/PriceGenerator/ru/release-2-2/)
