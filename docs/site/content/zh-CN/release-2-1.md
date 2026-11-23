---
layout: default
lang: zh-CN
route: release-2-1
title: "PriceGenerator 2.1 预发布版"
permalink: /zh-CN/release-2-1/
redirect_from:
  - /docs/site/content/zh-CN/release-2-1.html
---
# PriceGenerator 2.1 预发布版
{: id="pricegenerator-21-预发布" }

从 2.1 开始，同一组参数可以生成多条价格路径。每段行情都能单独复现，也可以在一张图上查看不同时刻各次模拟的收盘价分布。

- 每条路径都给出按收盘价计算的最大回撤。分位数曲线可以用来比较价格随时间推移的分散程度。
- 可选的 FuzzyRoutines 组件采用 Mamdani 模糊推理评估市场状态，并列出参与本次评分的规则。
- 写入 CSV 的速度有所提高，导出图表时占用的内存也更少。
- BTC/USD 示例用一个月的行情估计模型参数，再用下一个月的数据做样本外检验。[查看 Bitstamp 实验结果](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#bitstamp)

[从 GitHub 下载 2.1 预发布版](https://github.com/Fuzzy-Technologies/PriceGenerator/releases/tag/v2.1.0) · [旧版脚本迁移指南](https://fuzzy-technologies.com/PriceGenerator/zh-CN/migration/) · [2.2.1 版本说明](https://fuzzy-technologies.com/PriceGenerator/zh-CN/release-2-2/)

[English](../en/release-2-1.md) · [Русский](../ru/release-2-1.md)
