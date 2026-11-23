---
layout: default
lang: ru
route: quick-start
title: "Первые 240 свечей в PriceGenerator"
permalink: /ru/quick-start/
redirect_from:
  - /docs/site/content/ru/quick-start.html
---
# Первые 240 свечей в PriceGenerator
{: id="первый-прогон-pricegenerator" }

В этом примере вы получите четыре часа минутных котировок, откроете свечной график с индикаторами и проверите, что из сохранённых настроек можно получить точно такой же CSV. [Как устроена модель](https://fuzzy-technologies.com/PriceGenerator/ru/scenario-guide/) · [Что нового в 2.2.1](https://fuzzy-technologies.com/PriceGenerator/ru/release-2-2/)

## Установка PriceGenerator 2.2.1

Для [версии 2.2.1 на PyPI](https://pypi.org/project/pricegenerator/2.2.1/) подойдёт CPython 3.10–3.15. Создайте виртуальное окружение с помощью установленного у вас Python.

```sh
python -m venv .venv
```

В Windows PowerShell активируйте окружение командой `.\.venv\Scripts\Activate.ps1`. В Linux и macOS выполните `. .venv/bin/activate`. Затем установите пакет. Команда проверки версии должна вывести `2.2.1`.

```sh
python -m pip install pricegenerator==2.2.1
python -m pip check
python -I -c "from importlib.metadata import version; print(version('pricegenerator'))"
mkdir pg-example
cd pg-example
```

## Получить свечи, проверить CSV и построить график

```sh
python -I -m pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 60 --output prices.csv --manifest scenario.json
python -I -m pricegenerator validate prices.csv --timeframe-seconds 60 --no-gaps
python -I -m pricegenerator replay scenario.json --output replay.csv
python -I -m pricegenerator chart prices.csv --output chart.html --analysis --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

`generate` запишет котировки в `prices.csv`, а параметры и сведения об окружении — в `scenario.json`. Этот файл называется манифестом. Команда `validate` должна показать 240 строк и `"valid": true`. Значение `fingerprint` — контрольная сумма свечей. Сравните её с одноимённым полем манифеста.

`replay` заново строит ряд по манифесту и проверяет результат. В том же окружении файлы `prices.csv` и `replay.csv` совпадут побайтно.

Откройте **`chart.html`** в браузере. Свечи показывают цены, столбцы под ними — объём. Колесо мыши меняет масштаб, а **Box zoom** позволяет выделить мышью нужный участок. **Export PNG** сохранит видимый участок вместе с объёмом и выбранными индикаторами. Файл `chart.svg` удобно вставить в отчёт.

**Как включить индикаторы.** Добавьте `--analysis` при создании HTML, как в примере. В Python тот же режим включает `Chart(prices, "chart.html", analysis=True)`. В разделе **Indicators** выберите **SMA 50 / 200**. Первая скользящая средняя появится на 50-й минутной свече, вторая — на 200-й. **Bollinger bands** добавляет полосы Боллинджера, **Midpoint** отмечает середину между максимумом и минимумом каждой свечи. Там же доступны HMA, VWMA, PSAR, Alligator и Zig-Zag. Отдельные линии можно включать и выключать в **Individual series**. Кнопка **Light theme** переключает тему, а **Detailed statistics** раскрывает статистику ряда.

## Получить тот же ряд в Python
{: id="повторить-пример-из-python" }

В каталоге примера сохраните этот код в `scenario.py` и запустите `python -I scenario.py`.

```python
"""Reproduce a seeded minute-bar fixture using the installed package."""

from datetime import datetime, timezone

from pricegenerator import Chart, CreateManifest, Fingerprint, Generate, GenerationConfig, Replay, WriteCSV

config = GenerationConfig(
    seed=42,
    horizon=240,
    start=datetime(2025, 1, 6, tzinfo=timezone.utc),
    timeframe_seconds=60,
)
prices = Generate(config)
manifest = CreateManifest(config, prices)

if Fingerprint(Replay(manifest)) != Fingerprint(prices):
    raise RuntimeError("Replay changed the canonical OHLCV fingerprint")

WriteCSV(prices, "python-prices.csv", volume_as_count=True)
Chart(prices, "python-chart.svg", view=False)
Chart(prices, "python-analysis.html", analysis=True, view=False)
print(manifest["fingerprint"])
```

Программа напечатает ту же контрольную сумму, что и пример из командной строки. Чтобы совпали сами свечи, должны совпадать и начальное значение генератора случайных чисел (`seed`), и остальные настройки, включая время начала, интервал и версию модели.

## Как воспроизвести иллюстрацию
{: id="что-сохранить-рядом-с-графиком" }

Сохраните манифест, версию пакета, команду построения графика и её параметры. Контрольная сумма OHLCV покажет, совпали ли котировки. Если важно проверить сам файл изображения, отдельно сохраните его SHA-256. На байты PNG или JPEG могут влиять шрифты и версия программы отрисовки. Для графика Монте-Карло сохраните также число траекторий, способ задания их `seed` и выбранные квантили.

У [иллюстраций с индикаторами](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#charts) свой набор данных. Скрипт намеренно добавляет перерыв между торговыми сессиями и свечи с нулевым объёмом. Чтобы получить эти HTML и SVG, из корня репозитория на теге `v2.2.1` выполните `python -m tools.chart_examples --output-dir pg-figures --html`. [Исходный код примера](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.2.1/tools/chart_examples.py)

## Обмен барами с MetaTrader 5

PriceGenerator записывает CSV в UTF-8. Первая строка — `datetime,open,high,low,close,volume`. Дата и время указаны в UTC по ISO 8601, поля разделены запятыми, дробная часть — точкой. Если брокер выгрузил историю в местном времени, укажите исходный часовой пояс при импорте. Перерывы между торговыми сессиями сохраняйте. [Формат CSV](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#csv)

Для загрузки через `CustomRatesReplace` создайте в MT5 отдельный пользовательский символ. Подготовьте минутные бары (M1), как в этом примере. Время открытия должно приходиться на начало минуты. Поле `datetime` в MQL5 хранит целое число секунд с начала 1970 года. Перед загрузкой проверьте диапазон дат и укажите, историю за какой период нужно заменить.

Округлите цены до разрядности символа и проверьте, что открытие и закрытие по-прежнему лежат между минимумом и максимумом. Спред задайте в пунктах. Для теста синтетический объём можно записать в `tick_volume` как условное число тиков. Реальный торговый объём для `real_volume` берут из отдельного источника. Если количество актива дробное, сначала выберите единицу измерения, в которой его можно записать целым числом. [Структура MqlRates](https://www.mql5.com/ru/docs/constants/structures/mqlrates) · [Тип datetime](https://www.mql5.com/ru/docs/basis/types/integer/datetime)

После загрузки выгрузите несколько баров обратно из терминала и сверьте время, OHLC и объём с исходным CSV. Для режима тестера «Каждый тик на основе реальных тиков» понадобится история тиков. [CustomRatesReplace](https://www.mql5.com/ru/docs/customsymbols/customratesreplace) · [История пользовательского символа](https://www.mql5.com/ru/book/advanced/custom_symbols/custom_symbols_rates)

[English](../en/quick-start.md) · [简体中文](../zh-CN/quick-start.md)
