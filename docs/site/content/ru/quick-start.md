# Воспроизведение синтетического сценария OHLCV

![PriceGenerator от Fuzzy Technologies. Генератор синтетических рыночных данных.](../../../assets/pricegenerator-product-card.webp)

[English](../en/quick-start.md) · [简体中文](../zh-CN/quick-start.md)

Сгенерируем ряд с заданным seed, воспроизведём его по манифесту и построим
график без запуска браузера. Такой ряд подходит для тестирования программ и
управляемых экспериментов. Временные метки синтетические, а динамика цены
определяется параметрами модели.

## Установка из проверенного тега

Используйте CPython 3.10–3.13 и чистое окружение. Пример рассчитан на тестовый
тег GitHub `v2.0.0` с коммитом `83b1b75a99be06947a93314d6c2509a257ed6b3e`.

```sh
git clone --branch v2.0.0 --depth 1 https://github.com/Fuzzy-Technologies/PriceGenerator.git pg-demo
cd pg-demo
git rev-parse HEAD
python -m venv .venv
```

Активируйте окружение командой `. .venv/bin/activate` в POSIX-оболочке или
`.\.venv\Scripts\Activate.ps1` в Windows PowerShell. Из каталога репозитория
установите пакет с фиксированными версиями зависимостей. Проверка версии
должна вывести `2.0.0`.

```sh
python -m pip install -c requirements/modern.txt .
python -m pip check
python -I -c "from importlib.metadata import version; print(version('pricegenerator'))"
mkdir pg-example
cd pg-example
```

## Генерация, проверка и график

```sh
python -I -m pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 60 --output prices.csv --manifest scenario.json
python -I -m pricegenerator validate prices.csv --timeframe-seconds 60 --no-gaps
python -I -m pricegenerator replay scenario.json --output replay.csv
python -I -m pricegenerator chart prices.csv --output chart.html --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

Отчёт проверки содержит число строк (`240`), `"valid": true` и отпечаток
канонических данных OHLCV. Он совпадает с полем `fingerprint` в `scenario.json`. При воспроизведении
проверяются записанные настройки, версия библиотеки, окружение и точный
отпечаток данных. Содержимое двух CSV-файлов совпадает. Для просмотра и
масштабирования графика откройте локальный `chart.html`. Файл `chart.svg`
содержит статическое векторное изображение.

## Та же траектория из Python

Сохраните пример под именем `scenario.py` в рабочем каталоге и запустите
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

При том же окружении отпечаток данных совпадает с результатом CLI. Значение
`seed` задаёт поток случайных чисел, а полная конфигурация определяет модель, начало,
интервал и прочие параметры. Для повторения прогона сохраняйте манифест.

## Происхождение иллюстраций

Храните рядом с графиком тег или коммит исходников, манифест генерации,
команду отрисовки и её параметры. SHA-256 экспортированного файла записывайте
отдельно от отпечатка OHLCV. На растровый результат могут влиять версия
рендерера и шрифты. Для ансамбля также понадобятся seed отдельных траекторий
или правило их получения, число прогонов и способ агрегации.

Для готовых иллюстраций цены и индикаторов в репозитории используется другой
пример. Скрипт строит ряд с заданным seed, затем специально добавляет разрыв
торговой сессии и свечи с нулевым объёмом. Из корня репозитория на выбранном
теге запустите `python -m tools.chart_examples --output-dir pg-figures --html`,
чтобы заново получить SVG, HTML и описание примера.
[Скрипт построения](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/tools/chart_examples.py) · [Описание иллюстрации](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/examples/modern-market.md)

## Обмен барами с MetaTrader 5

PriceGenerator записывает UTF-8 CSV с заголовком
`datetime,open,high,low,close,volume`, метками ISO 8601 в UTC и конечными
числами с десятичной точкой. Для данных брокера заранее приведите формат к
этому виду и явно укажите часовой пояс, если в исходных метках нет смещения.
Сохраните разрывы торговых сессий и проверяйте их с учётом известного
интервала. [Контракт OHLCV и CSV](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/data-contract.md)

Адаптер для загрузки в пользовательский символ MT5 через `CustomRatesReplace`
принимает минутные бары с метками начала M1. Генерируйте M1 напрямую, как в
примере. Тип `datetime` в MQL5 использует целые секунды с 1970 года. Перед
преобразованием проверьте диапазон и выравнивание. Явно определите, как
перевести вещественный `volume` в целочисленные `tick_volume` и
`real_volume` и задать спред в пунктах. Зафиксируйте округление цены с учётом
разрядности символа и проверьте геометрию свечей после преобразования.
Используйте отдельный пользовательский символ и ограничьте заменяемый интервал.
[CustomRatesReplace](https://www.mql5.com/en/docs/customsymbols/customratesreplace) · [MqlRates](https://www.mql5.com/en/docs/constants/structures/mqlrates) · [MQL5 datetime](https://www.mql5.com/en/docs/basis/types/integer/datetime)

Этот пример проверяет CSV в Python. Загрузка в терминал, сверка баров после
обратного экспорта и настройки тестера требуют отдельной интеграционной
проверки. Для режима реальных тиков нужна отдельная история тиков.
[Руководство MQL5 по истории пользовательского символа](https://www.mql5.com/en/book/advanced/custom_symbols/custom_symbols_rates)
