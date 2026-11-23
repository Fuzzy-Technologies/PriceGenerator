---
layout: default
lang: ru
route: release-2-2
title: "PriceGenerator 2.2.1"
permalink: /ru/release-2-2/
redirect_from:
  - /docs/release-2-2-ru.html
---
# PriceGenerator 2.2.1

PriceGenerator создаёт свечи и объёмы для тестирования торговых программ. В версии 2.2 можно взять котировки с биржи, сравнить их со смоделированным рядом и измерить различия. Если тест выявил ошибку, отправьте коллеге настройки, CSV и график — он сможет повторить тот же эксперимент. [Установить 2.2.1 с PyPI](https://pypi.org/project/pricegenerator/2.2.1/)

## Что изменилось после 2.1
{: id="что-добавилось-после-21" }

- **Сравнение с рынком.** Команда `compare` сопоставляет два CSV с одним интервалом свечи. В отчёте видны различия в волатильности, просадке цены и объёме. Для интересующих показателей можно заранее задать допустимое отклонение.
- **Эксперимент, который можно повторить.** Готовый пример сохраняет два ряда свечей, их параметры, результаты сравнения и график Монте-Карло. Весь набор можно передать коллеге и проверить одной командой. [Запустить пример](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#bundle)
- **Целый объём в стандартной модели.** Значение под свечой показывает условную торговую активность за этот период. При загрузке реальной истории сохраняются исходные единицы и дробные значения, например объём торгов в BTC.

## Как читать график Монте-Карло
{: id="как-читать-график" }

Свечи и объёмы на рисунке показывают один из 32 смоделированных рядов. Для цветных линий использованы все ряды. Чтобы прочитать график, выберите один час и посмотрите, на каком уровне в это время проходила каждая линия.

![Свечи и объём первой траектории. Три линии показывают распределение часовых цен закрытия по 32 траекториям.](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-2-2-experiment-quantiles.svg)

Например, в последний час фиолетовая линия на отметке **101,27** — медиана 32 цен закрытия. Голубая и жёлтая линии на отметках **75,01** и **150,46** — 5-й и 95-й процентили. В соседнем часу эти значения считаются заново. По полосе видно, насколько к этому часу разошлись результаты при одной и той же начальной цене. [Как получить все 32 ценовых ряда](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#paths)

## Построить свой график
{: id="попробовать" }

Сгенерируйте 240 часовых свечей и откройте `candles.html` в браузере. Интернет для просмотра не нужен.

```sh
python -m pip install pricegenerator==2.2.1
pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --output candles.csv
pricegenerator chart candles.csv --output candles.html --analysis --no-view
```

Флаг **`--analysis`** добавляет панель индикаторов. Выберите **Bollinger bands** для полос Боллинджера или **SMA 50 / 200**, чтобы увидеть скользящие средние за 50 и 200 часов. В Python тот же режим включает `Chart(prices, "chart.html", analysis=True)`. Попробуйте выделить участок кнопкой **Box zoom** и сохранить его через **Export PNG**. [Все настройки графика](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#charts)

![Часовые свечи, полосы Боллинджера и две скользящие средние. Под ценой показан объём.](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-chart-analysis.webp)

[Быстрый старт](https://fuzzy-technologies.com/PriceGenerator/ru/quick-start/) · [Сравнить два CSV](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#compare) · [Перенести проект с 1.4.93](https://fuzzy-technologies.com/PriceGenerator/ru/migration/)

[English](https://fuzzy-technologies.com/PriceGenerator/en/release-2-2/) · [简体中文](https://fuzzy-technologies.com/PriceGenerator/zh-CN/release-2-2/)
