---
layout: default
lang: zh-CN
route: migration
title: "如何迁移旧版 PriceGenerator 脚本"
permalink: /zh-CN/migration/
redirect_from:
  - /docs/site/content/zh-CN/migrate-to-2-1.html
---
# 如何迁移旧版 PriceGenerator 脚本
{: id="迁移到-pricegenerator-21" }

1.4.93 和 2.x 使用不同的生成模型和调用方式。如果还要复查以前的实验，请连同输入、输出一起保留当时的软件环境。新项目可以从[安装 2.2.1](https://fuzzy-technologies.com/PriceGenerator/zh-CN/quick-start/)开始。

| 版本     | 适用情况                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------- |
| `1.4.93` | 需要复现用 1.x 接口得到的结果时，可从 PyPI 安装此历史版本。                                    |
| `v2.0.0` | 最早一批 2.x 示例使用的 GitHub 测试版本，对应提交 `83b1b75a99be06947a93314d6c2509a257ed6b3e`。 |
| `v2.1.0` | 加入了蒙特卡洛模拟和可选的模糊诊断，可从 GitHub 下载当时的预发布版本。                         |

## 从 1.4.93 迁移

为当前版本单独创建 CPython 3.10–3.15 环境。以前需要逐个设置生成器对象的属性，现在将参数写入 `GenerationConfig`，再调用 `Generate(config)`。命令行改用 `generate` 子命令。由于模型算法已改变，沿用旧的随机种子也无法得到与 1.x 相同的行情。生成新数据后，请另存运行清单。

如果只想查看原有行情，可将已有 CSV 转为 `datetime,open,high,low,close,volume` 六列，将时间转换为 UTC，随后运行 `validate` 或 `chart`。[CSV 格式](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#csv) · [图表设置](https://fuzzy-technologies.com/PriceGenerator/zh-CN/reference/#charts)

## 从 2.0 测试版迁移
{: id="从-v200-测试版迁移" }

保留 2.0 清单及当时的软件环境，供以后复现实验。迁移后，用相同参数重新生成行情，先比较 OHLCV 数据的校验值，再核对导出的图表文件。基础包支持 SVG 和离线 HTML，直接导出 PNG 或 JPEG 时需要安装 `export` 扩展。在自动化脚本中可用 `--no-view` 阻止浏览器自动打开，Python 参数为 `view=False`。[模型原理](https://fuzzy-technologies.com/PriceGenerator/zh-CN/scenario-guide/)

## 迁移完成后怎样核对结果？
{: id="验证固定种子的样例" }

请在新的目录中运行以下命令。需要核对历史版本 2.1 时，可下载[当时的预发布包](https://fuzzy-technologies.com/PriceGenerator/zh-CN/release-2-1/)。已安装 2.2.1 的用户也可以用这些命令验证当前环境。

```sh
python -I -m pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 60 --output prices.csv --manifest scenario.json
python -I -m pricegenerator validate prices.csv --timeframe-seconds 60 --no-gaps
python -I -m pricegenerator replay scenario.json --output replay.csv
python -I -m pricegenerator chart prices.csv --output chart.html --analysis --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

校验应显示 240 行有效的分钟行情。在同一环境中，`prices.csv` 和 `replay.csv` 的内容应逐字节相同。打开 `chart.html`，选择 **Bollinger bands** 就能查看布林带。图中的指标开关由 `--analysis` 启用，对应的 Python 参数为 `analysis=True`。[2.0 命令行演示（GIF）](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-cli-demo.gif)

[English](../en/migrate-to-2-1.md) · [Русский](../ru/migrate-to-2-1.md)
