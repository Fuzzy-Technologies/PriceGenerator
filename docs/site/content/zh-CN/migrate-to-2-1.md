# 迁移到 PriceGenerator 2.1

[English](../en/migrate-to-2-1.md) · [Русский](../ru/migrate-to-2-1.md)

| 版本     | 用途                                                                                |
| -------- | ----------------------------------------------------------------------------------- |
| `1.4.93` | 历史 PyPI 版本，也是从 1.x 迁移的起点。                                             |
| `v2.0.0` | 新版运行时的 GitHub 测试标签，对应提交 `83b1b75a99be06947a93314d6c2509a257ed6b3e`。 |
| `2.1.0`  | GitHub 预发布版本，提供蒙特卡洛实验、可选模糊诊断和更快的导出。                     |

## 从 1.4.93 迁移

如需复现 1.x 实验，请保留旧环境、输入文件和输出结果。为新版软件包单独创建
CPython 3.10–3.13 环境。使用 `GenerationConfig` 和 `Generate(config)`
替换旧的可变生成器对象。将旧的 CLI 参数改为 `generate` 子命令。
运行 `validate` 或 `chart` 前，请将原文件转换为采用 UTC 时间的标准
OHLCV 格式，表头为 `datetime,open,high,low,close,volume`。
旧种子属于旧模型。请为 v2 样例保存新的清单。
[数据约定](../../../data-contract.md) · [API 与图表迁移](../../../chart-migration.md)

## 从 v2.0.0 测试版迁移

保留测试版的清单和环境，以便精确复现原有运行结果。评估 2.1 时，请在干净
的安装环境中使用相同配置重新生成样例，比较 OHLCV 指纹，并单独检查图表文件。
核心安装支持独立的 SVG 文件和可离线使用的交互式 HTML。自动化运行时，
CLI 使用 `--no-view`，Python 使用 `view=False`。导出 PNG 或 JPEG
需要安装与软件包版本匹配的 `export` 扩展。
[模型假设与局限](../../../model-regime-v2.md)

## 验证固定种子的样例

从 [GitHub 预发布页面](release-2-1.md) 下载并安装 2.1，
然后在新的输出目录中运行以下命令。

```sh
python -I -m pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 60 --output prices.csv --manifest scenario.json
python -I -m pricegenerator validate prices.csv --timeframe-seconds 60 --no-gaps
python -I -m pricegenerator replay scenario.json --output replay.csv
python -I -m pricegenerator chart prices.csv --output chart.html --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

验证应确认全部 240 行数据有效。在清单记录的环境中，
`prices.csv` 与 `replay.csv` 逐字节一致。
[CLI 动画示例](../../../examples/cli-demo.md) 使用的是另一组 2.0.0 样例数据。
配套说明记录了命令、导出参数和复现步骤。
