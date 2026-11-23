---
layout: default
lang: zh-CN
route: reference
title: "K 线数据使用手册"
permalink: /zh-CN/reference/
redirect_from:
  - /docs/site/content/zh-CN/reference.html
---
# K 线数据使用手册

## CSV 格式与成交量
{: #csv }

表头为 `datetime,open,high,low,close,volume`。时间戳使用 UTC，唯一且递增。导入券商数据时，若时间戳不含时区，须明确指定。最高价和最低价要覆盖开盘价和收盘价。使用 `--timeframe-seconds 3600 --no-gaps` 可检查小时线是否连续。

默认模型生成整数活动量。导入的资产数量保留原始单位，可以是小数。在 Python 中使用 `WriteCSV(candles, "candles.csv", volume_as_count=True)`，生成的整数活动量便会与 CLI 写入完全相同的文本。

## 图表与指标
{: #charts }

基础 HTML 图表显示 K 线和成交量。加入 `--analysis` 即可使用指标开关和可展开的统计报告。200 周期均线至少需要 200 根 K 线。布林带显示均线附近的波动范围，Midpoint 标记每根 K 线最高价和最低价的中点。最高和最低收盘价线、首尾收盘价趋势线和 Zig-Zag 都会用到后续数据，适合回看已完成的走势。

```sh
python -m pricegenerator chart candles.csv --analysis --output chart.html --view
```

用滚轮或框选放大查看某一时段。**Export PNG** 保存当前视图及已选指标。直接导出 PNG/JPEG 需要安装 `pricegenerator[export]`。静态导出若使用 `--analysis`，图下还会附上完整统计报告。SVG 和离线 HTML 可用基础安装生成。

## 分布与回撤
{: #analysis }

运行 `python -m pricegenerator analyze candles.csv --output stats.json` 可以统计涨跌、收益率、成交量、尾部和序列相关性。按收盘价计算的价格回撤反映从先前收盘高点到随后收盘价的跌幅。策略账户回撤还取决于仓位和交易成本。报告会说明某些指标为何无定义。

## 模型参数
{: #model }

漂移和波动参数按每根 K 线设置。将间隔从分钟改为小时只会改变时间戳的间距，需要另行选择适合新周期的波动参数。生成器输出 K 线和合成活动量。交易日历、买卖价差、逐笔行情和订单成交需要其他数据。[阅读 K 线和活动量的生成步骤](https://fuzzy-technologies.com/PriceGenerator/zh-CN/scenario-guide/)。

## 研究功能
{: #research }

Python 接口可在较早的时间窗口内估计部分参数，并在后续窗口中检验。受限的连续成交量拟合会将活动量固定为训练均值。使用 CPython 3.13–3.15 可选装模糊诊断，根据波动和活动量输出单独评分。该评分不参与价格生成。[查看 BTC/USD 实验结果](https://fuzzy-technologies.com/PriceGenerator/zh-CN/experiments/#bitstamp)。

## 构建和验证
{: #development }

在源码目录运行 `python -m pip install .` 安装本地版本。需要公开 Python API 参考时，安装 `.[docs]`，然后在仓库根目录运行 `python PDocBuilder.py`。生成的入口为 `build/docs-api/pricegenerator.html`。旧版本的生成器使用可变对象和不同的 CLI 参数。[迁移已有脚本](https://fuzzy-technologies.com/PriceGenerator/zh-CN/migration/)。


## 验证实验结果
{: #validation }
分别检查 CSV 结构、分布和相邻 K 线间的依赖关系。即使波动率相近，成交量以及剧烈波动的聚集程度仍可能不同。用早期数据设定容差，并在后续时段检验。保存随机种子、清单和数据指纹。

## 安装与发布
{: #packaging }
项目构建 wheel 和源码包，发布到 PyPI 前会在干净环境中验证安装。发布标签记录了源码提交。基础包支持离线 HTML 和 SVG，PNG 和 JPEG 需安装 export 扩展。

[English](../en/reference.md) · [Русский](../ru/reference.md)
