# PriceGenerator

![Алиса на обложке PriceGenerator, генератора котировок Fuzzy Technologies.](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-product-card.webp)

[English](https://fuzzy-technologies.com/PriceGenerator/) · [Русский](https://fuzzy-technologies.com/PriceGenerator/ru/) · [简体中文](https://fuzzy-technologies.com/PriceGenerator/zh-CN/) · [Быстрый старт](https://fuzzy-technologies.com/PriceGenerator/ru/quick-start/)

PriceGenerator генерирует котировки для тестирования торговых программ. Задайте начальную цену, интервал свечи и волатильность, чтобы получить свечи и объём в CSV. Один и тот же ряд можно использовать после каждой правки программы, а несколько разных рядов — загрузить в свой тестер и сравнить результаты стратегии.

## Что можно попробовать

- **Проверить импорт котировок.** Подготовьте CSV из 240 свечей. Загрузите его до и после изменения импортёра, затем сравните даты, цены и объёмы. [Получить тестовый файл](https://fuzzy-technologies.com/PriceGenerator/ru/quick-start/)
- **Проверить индикатор.** На графике с `--analysis` включите две скользящие средние и посмотрите, на каких свечах появляются их первые значения. [Открыть график с индикаторами](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#charts)
- **Проверить стратегию при разном движении цены.** Смоделируйте 32 ряда при одинаковых настройках. Для каждого запустите свой тестер с теми же правилами входа и выхода. [Пример Монте-Карло](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#monte-carlo)
- **Сравнить модель с рынком.** В примере BTC/USD модель настроили по сентябрьским торгам на Bitstamp и проверили на октябрьских. Все 16 прогонов уложились в допуски по волатильности и среднему часовому объёму. Но на бирже объём менялся от часа к часу, а в модели оставался постоянным. [Результаты эксперимента](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#bitstamp)

## Установка

Для [PriceGenerator 2.2.1](https://pypi.org/project/pricegenerator/2.2.1/) подойдёт CPython 3.10–3.15. Базовой установки достаточно для CSV, интерактивного HTML и SVG. Вторая команда понадобится для прямого экспорта в PNG и JPEG.

```bash
python -m pip install pricegenerator==2.2.1
python -m pip install 'pricegenerator[export]==2.2.1'  # Для экспорта в PNG и JPEG.
```

Если вы скачали исходники, из корня репозитория выполните `python -m pip install .`. [Что нового в 2.2.1](https://fuzzy-technologies.com/PriceGenerator/ru/release-2-2/) · [Предыдущие выпуски](https://github.com/Fuzzy-Technologies/PriceGenerator/releases)

## Сгенерировать свечи и записать CSV

```python
from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV

config = GenerationConfig(seed=0, horizon=240, volatility=0.01)
prices = Generate(config)
WriteCSV(prices, "prices.csv", volume_as_count=True)
restored = ReadCSV("prices.csv")
```

Время начала ряда по умолчанию фиксировано и задано в UTC. Начальное значение генератора случайных чисел задаёт `seed`. Ноль — обычное допустимое значение. При тех же настройках в том же окружении вы получите те же свечи. У каждого вызова свой генератор случайных чисел. Чтобы поменять параметры, создайте новую конфигурацию.

Стандартная модель `regime_v3` записывает объём целым числом в условных единицах активности. Для повторения старых сценариев с дробным объёмом доступна `model="regime_v2"`. [Как строится следующая свеча и чем отличается алгоритм 1.4.93](https://fuzzy-technologies.com/PriceGenerator/ru/scenario-guide/)

Таблица OHLCV содержит шесть столбцов: `datetime,open,high,low,close,volume`. Время открытия хранится в UTC с наносекундной точностью. Цены и объём имеют тип `float64`. Если источник записал время без смещения, укажите исходный часовой пояс. Функция `ValidateOHLCV` возвращает проверенную копию таблицы. С её помощью можно также проверить интервал между свечами и пропуски. [Формат CSV](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#csv)

## Повторить прогон и посмотреть результат

```python
import json
from pricegenerator import Analyze, Chart, CreateManifest, Indicators, Replay

manifest = CreateManifest(config, prices)
with open("scenario.json", "w", encoding="utf-8") as stream:
    json.dump(manifest, stream, allow_nan=False, indent=2)
replayed = Replay(manifest)
statistics = Analyze(prices).ToDict()
indicators = Indicators(prices).ToDict()
chart_path = Chart(prices, "chart.html", analysis=True, view=False)
```

Сохраните вместе с CSV файл `scenario.json`. Это манифест — запись настроек модели, версии пакета, генератора случайных чисел и окружения. В нём также есть контрольные суммы сценария и самих свечей. По умолчанию `Replay` проверяет совпадение окружения. Чтобы проверить воспроизводимость в другом окружении, передайте `strict_environment=False`. Версия пакета и обе контрольные суммы по-прежнему должны совпадать.

`Analyze` рассчитывает статистику, `Indicators` — технические индикаторы. Исходная таблица сохраняется. Если показатель не определён, в отчёте будет указана причина. [Статистика ряда и просадка цены](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#analysis)

`Chart(prices)` открывает интерактивный график в браузере. Его можно просматривать без интернета. С параметром `view=False` файл сохранится без открытия браузера. Расширение файла определяет формат, а `analysis=True` добавляет индикаторы и статистику. В Jupyter используйте `DisplayChart(prices)`. При необходимости установите дополнение `notebook`. [Управление графиком](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#charts)

## Те же операции из командной строки

```bash
pricegenerator generate --seed 0 --horizon 240 --output prices.csv --manifest scenario.json
pricegenerator replay scenario.json --output replay.csv
pricegenerator validate prices.csv --timeframe-seconds 3600 --no-gaps
pricegenerator analyze prices.csv --output statistics.json
pricegenerator chart prices.csv --output chart.html --no-view --analysis
```

**Как включить индикаторы.** Укажите `--analysis` при создании HTML или `analysis=True` при вызове `Chart` из Python. Откройте `chart.html` и выберите в разделе **Indicators** полосы Боллинджера (**Bollinger bands**) или скользящие средние (**SMA 50 / 200**). Для средней за 200 периодов потребуется не менее 200 свечей. **Midpoint** отмечает середину между максимумом и минимумом каждой свечи. В списке есть также HMA, VWMA, PSAR, Alligator и Zig-Zag. Отдельную линию можно отключить в **Individual series**.

Колёсико меняет масштаб. **Box zoom** увеличивает выделенный участок, **Light theme** включает светлую тему, **Export PNG** сохраняет видимые свечи и объёмы с выбранными индикаторами. В разделе **Detailed statistics** находится подробная статистика.

![Часовые свечи с полосами Боллинджера и средними за 50 и 200 часов. Под графиком видны объёмы.](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-chart-analysis.webp)

Если команда `pricegenerator` недоступна по имени, используйте `python -m pricegenerator`. Параметры генерации можно сохранить в JSON и передать через `--config`. Значения, явно заданные в командной строке, заменяют соответствующие значения в файле. CLI проверяет названия параметров, числовые значения, однозначность времени и пути к файлам.

В версии 2.1 появились команды для многократного моделирования по методу Монте-Карло и повторения отдельных траекторий. На CPython 3.13–3.15 дополнительно доступна нечёткая оценка состояния рынка. [Эксперименты](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#monte-carlo) · [Нечёткая диагностика](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#research)

В ветке 2.x изменились класс генератора, команды запуска и вызовы для построения графиков. [Как перенести скрипты с 1.4.93](https://fuzzy-technologies.com/PriceGenerator/ru/migration/)

## Сравнить два ряда свечей

`pricegenerator compare` сравнивает два ряда OHLCV с одинаковым интервалом свечи. В отчёте приводятся показатели обоих рядов, их контрольные суммы и результаты проверки по заданным допускам. В готовом примере можно сгенерировать оба ряда, повторить эксперимент и построить график с разбросом цен по 32 траекториям. [Сравнить CSV](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#compare) · [Повторить весь эксперимент](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#bundle)

## Разработка и расширения

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
```

Инструкции для разработчиков собраны в `AGENTS.md` в корне репозитория. [Сборка справочника API](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#development) · [Сборка пакета](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#packaging) · [Проверка модели](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#validation)

В Python доступны экспериментальные модули `pricegenerator.calibration`, `pricegenerator.evaluation`, `pricegenerator.extended_models` и `pricegenerator.registry` для оценки параметров, сравнения с историей и работы с другими моделями. Большие ряды можно генерировать и записывать по частям с помощью `GenerateChunks` и `WriteCSVChunks`.

[Репозиторий](https://github.com/Fuzzy-Technologies/PriceGenerator) · [Задачи](https://github.com/Fuzzy-Technologies/PriceGenerator/issues) · [Лицензия Apache-2.0](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.2.1/LICENSE)
