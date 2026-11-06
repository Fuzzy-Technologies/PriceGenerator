# Первый прогон PriceGenerator

![PriceGenerator от Fuzzy Technologies. Генератор синтетических рыночных данных.](../../../assets/pricegenerator-product-card.webp)

[English](../en/quick-start.md) · [简体中文](../zh-CN/quick-start.md)

[Модель и границы применимости](scenario-guide.md) · [Обзор 2.1](release-2-1.md)

Сгенерируем 240 минутных баров, повторим прогон по манифесту и сохраним
два графика. Такой ряд можно использовать в тестах импортёра, расчёта
индикаторов или отчётности. Временную сетку задаёт конфигурация, а цены
и объём рассчитывает модель.

## Установить версию из примера

Для контрольного прогона возьмите CPython 3.10–3.13 и тестовый тег
`v2.0.0`. Команда `git rev-parse HEAD` должна вывести
`83b1b75a99be06947a93314d6c2509a257ed6b3e`.

```sh
git clone --branch v2.0.0 --depth 1 https://github.com/Fuzzy-Technologies/PriceGenerator.git pg-demo
cd pg-demo
git rev-parse HEAD
python -m venv .venv
```

Активируйте окружение командой `. .venv/bin/activate` в POSIX-совместимой
оболочке или `.\.venv\Scripts\Activate.ps1` в Windows PowerShell. Установите
пакет из каталога репозитория с версиями зависимостей из
`requirements/modern.txt`. Проверка версии должна вывести `2.0.0`.

```sh
python -m pip install -c requirements/modern.txt .
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
python -I -m pricegenerator chart prices.csv --output chart.html --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

Проверка должна вернуть 240 строк, `"valid": true` и контрольный хеш OHLCV,
равный полю `fingerprint` в `scenario.json`. При повторе пакет сверяет
настройки, версию, окружение и хеш данных. `prices.csv` и `replay.csv`
должны совпасть побайтно. Откройте `chart.html` в браузере, чтобы менять
масштаб и смотреть значения свечей. `chart.svg` — статический векторный
график.

## Повторить пример из Python

Сохраните код как `scenario.py` в каталоге примера и запустите
`python -I scenario.py`.

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

WriteCSV(prices, "python-prices.csv")
Chart(prices, "python-chart.svg", view=False)
print(manifest["fingerprint"])
```

В том же окружении программа выведет тот же хеш OHLCV, что и CLI.
`seed` задаёт поток случайных чисел. Чтобы получить тот же ряд,
нужны также модель, начало ряда, интервал и остальные настройки.
Все параметры прогона сохраняются в манифесте.

## Что сохранить рядом с графиком

Запишите тег или коммит, приложите манифест и команду построения графика
с параметрами. Хеш SHA-256 файла экспорта храните отдельно от хеша OHLCV.
Первый проверяет байты файла, которые у PNG и JPEG могут зависеть от версии
рендерера и шрифтов. Второй проверяет свечи. Для графика Монте-Карло
запишите также число траекторий, их `seed` или правило расчёта этих значений
и способ агрегации.

В примерах цены и индикаторов из репозитория используется другой ряд.
Скрипт генерирует свечи с фиксированным `seed`, затем специально добавляет
разрыв торговой сессии и бары с нулевым объёмом. Чтобы собрать SVG, HTML
и описание прогона, выполните из корня репозитория на теге `v2.0.0`
`python -m tools.chart_examples --output-dir pg-figures --html`.
[Скрипт](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/tools/chart_examples.py) ·
[Параметры примера](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/examples/modern-market.md)

## Обмен барами с MetaTrader 5

PriceGenerator пишет CSV в UTF-8 с заголовком
`datetime,open,high,low,close,volume`. Метки времени записываются в UTC
по ISO 8601, разделитель полей — запятая, десятичный разделитель — точка.
Перед импортом истории брокера приведите её к этому формату. Если
в исходных метках нет смещения, укажите часовой пояс. Сохраняйте разрывы
между торговыми сессиями и проверяйте пропуски с учётом интервала ряда.
[Формат OHLCV и CSV](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/data-contract.md)

Для загрузки в пользовательский символ через `CustomRatesReplace` нужны
минутные бары с метками открытия, кратными минуте. Генерируйте M1 напрямую,
как в примере. В MQL5 `datetime` хранит целое число секунд с начала
1970 года. Перед преобразованием проверьте диапазон и попадание в минутную
сетку. В коде импорта задайте, как из вещественного `volume` получить
целочисленные `tick_volume` и `real_volume`, и откуда берётся спред
в пунктах. Округлите цены до разрядности символа и ещё раз проверьте
соотношение `open`, `high`, `low` и `close`. Используйте отдельный
пользовательский символ и ограничьте период замены баров.
[CustomRatesReplace](https://www.mql5.com/en/docs/customsymbols/customratesreplace) ·
[MqlRates](https://www.mql5.com/en/docs/constants/structures/mqlrates) ·
[Тип datetime](https://www.mql5.com/en/docs/basis/types/integer/datetime)

Пример проверяет CSV в Python. Импорт в терминал, сверку после обратной
выгрузки и настройки тестера проверяйте отдельно. Для теста в режиме
реальных тиков загрузите отдельную тиковую историю.
[История пользовательских символов в MQL5](https://www.mql5.com/en/book/advanced/custom_symbols/custom_symbols_rates)
