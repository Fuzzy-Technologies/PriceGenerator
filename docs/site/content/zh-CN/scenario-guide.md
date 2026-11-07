# 合成 OHLCV 场景及其适用范围

[English](../en/scenario-guide.md) · [Русский](../ru/scenario-guide.md)

按照[快速入门](quick-start.md)，可从已验证的 GitHub 2.0 测试基线生成、
重放并导出分钟 K 线。[迁移指南](migrate-to-2-1.md)介绍 2.1.0 的变更。
2.1.0 是 GitHub 预发布版本。

## 理解 K 线数据

可交换的数据表按顺序包含六列
`datetime,open,high,low,close,volume`。时间戳唯一、严格递增，
并以纳秒精度表示 UTC 时刻。价格和成交量为有限的 binary64 数值。
成交量非负，最高价和最低价的范围覆盖开盘价与收盘价。
只要满足 K 线的几何约束，标准读取接口就接受非正价格。
默认生成器只产生正价格。

验证规则时间网格时需显式给出间隔。处理经纪商数据时，请指定不带
时区偏移的时间戳所用的时区，并保留实际存在的间断。解析和验证规则
见 [CSV 约定](../../../data-contract.md)。与 MT5 交换数据时，请参阅
[交换示例](quick-start.md#与-metatrader-5-交换-k-线)中的 M1 时间对齐、
整型成交量字段和点差设置。采用真实逐笔报价的策略测试需要独立的
逐笔历史数据。

## 构建可控的合成场景

`regime_v2` 从低波动状态开始。生成每根 K 线之前，模型以
`1 - regime_persistence` 的概率在低波动和高波动状态之间切换。
低波动状态下，收益率高斯分量的标准差 $\sigma$ 为 `volatility`，高波动状态下
为 `volatility * regime_scale`。参数按单根 K 线定义，改变时间间隔时
应为新的采样频率选择参数。

模型提出的对数收益率为
$r = \mu + \sigma Z + \sigma_0 s B Z_{\mathrm{shock}}$。
其中 $\mu$ 是 `drift`，$\sigma_0$ 是基础波动率 `volatility`，
$s$ 是 `shock_scale`。两个正态随机量相互独立，独立的伯努利随机量
$B$ 以 `shock_probability` 的概率激活冲击。从第二根 K 线起，
开盘价等于上一根的收盘价。如果拟定的对数收盘价超出配置边界，
模型会进行反射。因此，实现的对数收益率可能与 $r$ 不同。

上下影线在对数价格空间从实体向外延伸。两侧的异常延长事件相互独立，
影线受价格边界截断。成交量是连续的市场活跃度指标，其对数噪声具有
自相关，并可与实际对数收益率的绝对值耦合。[模型规范](../../../model-regime-v2.md)
列出完整公式、随机抽样顺序和边界规则。[数值测试](../../../../tests/test_regime_v2_oracles.py)
包含用手工推导值校验的场景。

## 检查结果并保留来源记录

在快速入门的示例目录中运行以下命令。

```sh
python -I -m pricegenerator analyze prices.csv --output statistics.json
python -I -m pricegenerator chart prices.csv --output analysis.html --analysis --no-view
```

第一条命令写入统计结果，并标明无法定义的估计量。第二条命令生成含
指标和诊断信息的离线 HTML 图表，可在本地打开查看。
[分析指南](../../../analysis.md)定义了指标和无法计算的情形。

**如何显示指标按钮？** 用同一份 CSV 重新生成 HTML，并加上 `--analysis`。
在 Python 中可以调用 `Chart(prices, "chart.html", analysis=True)`。
用浏览器打开文件后，点击 **Bollinger bands** 查看均线周围的波动范围，
点击 **SMA 50 / 200** 比较两条均线，或点击 **Midpoint** 标出每根 K 线
最高价与最低价的中点。还可以切换 HMA、VWMA、PSAR、Alligator 和 Zig-Zag。
展开 **Individual series** 可以单独开关一条曲线。SMA 200 至少需要 200 根 K 线。

用滚轮或 **Box zoom** 放大选定区间。**Light theme** 切换至浅色主题，
**Export PNG** 保存当前视图。图表下方显示简要概览，展开
**Detailed statistics** 可查看完整报告。

![离线 K 线和成交量图，已开启布林带及 50 和 200 周期均线](../../../assets/pricegenerator-chart-analysis.webp)

记录源码标签或提交、完整配置和种子、清单文件、命令、依赖版本，
以及各导出文件的 SHA-256。清单中的 K 线指纹标识标准化数据；
导出哈希标识文件字节，可能随渲染环境而变。
[市场图示例](../../../examples/modern-market.md)和
[指标对齐示例](../../../examples/modern-indicator-alignment.md)给出生成与转换
数据的步骤。[CLI 动画示例](../../../examples/cli-demo.md)使用另一组
120 根 K 线，并记录了相应命令和来源。

## 明确研究 API 的假设

- [校准、区块自助法和脚本化压力场景](../../../research-models.md)
  通过实验性模块 API 提供，并附有可重现的合成数据证据。
- [蒙特卡洛](../../../monte-carlo.md)介绍实验性的固定种子集合模拟，
  以及每个时点的价格分位数。分位数取决于所选模型，
  逐时点区间无法保证对整条路径的同时覆盖。
- [模糊诊断](../../../fuzzy-diagnostics.md)是 Python 3.13–3.15 上的可选实验功能。
  标量得分概括输入的波动率和活跃度比值，不会反过来改变 K 线生成。
- [参考数据比较](../../../reference-comparison.md)记录历史样例的来源、
  假设和限制。分别检验结构、边际统计量和依赖关系。
  [统计证据原则](../../../adr/0005-statistical-validation-and-realism-claims.md)
  说明作出更强结论需要哪些证据。

默认模型适用于 OHLCV 消费端的受控测试和压力场景。模型不包含订单簿、
点差、成交机制或交易所日历。其输出无法证明预测能力或策略收益。

从同一份源码构建[公共 Python API 参考](../../../development.md#build-the-public-api-reference)，
即可查看根模块的导出项及函数签名。
