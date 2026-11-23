---
layout: default
lang: ru
route: experiments
title: "Эксперименты с синтетическими котировками"
permalink: /ru/experiments/
redirect_from:
  - /docs/site/content/ru/experiments.html
---
# Эксперименты с синтетическими котировками

## Повторить один сценарий 32 раза
{: #monte-carlo }

Оставим одну начальную цену и одни настройки модели. Каждая траектория получит свою воспроизводимую последовательность случайных движений. В `quantiles.html` свечи и объёмы относятся к первому прогону. Три линии показывают 5-й, 50-й и 95-й процентили всех закрытий в каждом часу. Для последнего часа этого примера на 120 барах получаются 75,01, 101,27 и 150,46. Отдельная траектория может пересечь границу в другом часу.

```sh
python -m pricegenerator monte-carlo --seed 42 --paths 32 --horizon 120 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --output ensemble.json --manifest ensemble-manifest.json --chart quantiles.html
python -m pricegenerator replay-ensemble ensemble-manifest.json --output replayed.json
```

В JSON есть максимальная ценовая просадка каждой траектории. Для проверки входов, выходов и издержек восстановите каждый ряд и прогоните своё правило в тестере.

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

## Сравнить синтетику с наблюдениями
{: #compare }

Подготовьте два CSV с заголовком OHLCV, одинаковым таймфреймом и сопоставимыми единицами объёма. Выберите непрерывные участки с постоянным шагом. Через `--tolerances` можно передать JSON с абсолютными допусками для отдельных показателей. Успешное завершение команды означает, что сравнение выполнено. Какие показатели уложились в допуски, видно в отчёте.

```sh
python -m pricegenerator compare observed.csv synthetic.csv --timeframe-seconds 3600 --output comparison.json
```

## На какой рынок похож этот ряд?
{: #bitstamp }

У базового сценария нет тикера. Стартовая цена по умолчанию — 100. Чтобы приблизить отдельные свойства реального рынка, выберите инструмент и таймфрейм, настройте модель по ранней истории и проверьте на следующем периоде. В эксперименте на часовых данных BTC/USD с Bitstamp для подгонки взяли 720 баров сентября 2024 года, а для проверки — 744 бара октября. Все 16 прогонов уложились в заданные допуски по волатильности доходностей и среднему часовому объёму в BTC.

Ограниченная подгонка `regime_v2` дала постоянный объём 71,93 BTC в час. На бирже среднее составило 67,45 BTC, а объём заметно менялся вместе с величиной ценового движения (корреляция 0,522). У постоянной величины такая корреляция не определена. Отличалась и склонность резких движений следовать друг за другом. На таком примере можно воспроизвести выбранные свойства рынка и измерить, где сходство заканчивается. В обычной генерации `regime_v3` получаются меняющиеся целые значения активности. [Числовые результаты и происхождение данных](https://fuzzy-technologies.com/PriceGenerator/docs/evidence/reference-bitstamp-holdout.json).

## Передать коллеге весь эксперимент
{: #bundle }

Из корня репозитория той же версии, что и установленный пакет, запустите готовый скрипт. Укажите новую папку. В ней появятся два синтетических часовых ряда, их манифесты, отчёт сравнения, график по 32 траекториям и контрольные суммы. Вторая команда сверит сохранённые файлы.

```sh
python -I tools/experiment_bundle.py create pg-experiment
python -I tools/experiment_bundle.py verify pg-experiment
```

Откройте `pg-experiment/quantiles.html`. Для графика с индикаторами выполните `python -m pricegenerator chart pg-experiment/scenario.csv --analysis --output analysis.html --view`. В примере 120 свечей. Для SMA 200 возьмите 240 свечей из [быстрого старта](https://fuzzy-technologies.com/PriceGenerator/ru/quick-start/).

[English](../en/experiments.md) · [简体中文](../zh-CN/experiments.md)
