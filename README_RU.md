# PriceGenerator

[English](https://fuzzy-technologies.com/PriceGenerator/) · [Русский](https://fuzzy-technologies.com/PriceGenerator/ru/) · [简体中文](https://fuzzy-technologies.com/PriceGenerator/zh-CN/) · [Быстрый старт](https://fuzzy-technologies.com/PriceGenerator/ru/quick-start/)


PriceGenerator строит синтетические ряды свечей OHLCV для тестирования
торговых систем и количественных экспериментов. Можно задать параметры
рынка, сохранить свечи в CSV, повторить прогон и посмотреть результат
на графике. Для оценки прогнозов и доходности стратегии нужна отдельная
проверка на рыночных данных.

На [русском сайте проекта](https://fuzzy-technologies.com/PriceGenerator/ru/) есть быстрый старт, описание модели и эксперименты с историческими данными.

## Что можно попробовать

- **Проверить импорт котировок.** Сгенерируйте 240 свечей с фиксированным `seed` и сохраните манифест. После изменения кода повторите прогон и сравните файлы.
- **Проверить индикатор на графике.** Откройте офлайн-график с `--analysis` и включите полосы Боллинджера или SMA 50 / 200 на одних и тех же свечах.
- **Испытать торговое правило.** Прогоните свою стратегию на нескольких ценовых траекториях в собственном тестере. Сам генератор покажет разброс цен закрытия и просадки смоделированной цены.
- **Сопоставить сценарий с рынком.** Возьмите часовую историю BTC/USD без пропусков, подберите параметры на раннем периоде и сравните волатильность и объём на следующем. В [примере Bitstamp](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#bitstamp) видно, какие свойства удалось воспроизвести. Базовый сценарий начинается со 100 и не привязан к инструменту.

На часовых BTC/USD с Bitstamp все 16 прогонов уложились в заданные допуски по волатильности доходностей и среднему объёму на следующем месяце. У подогнанной модели объём оставался постоянным. На бирже он менялся вместе с величиной ценового движения.

## Установка

[PriceGenerator 2.2.1 на PyPI](https://pypi.org/project/pricegenerator/2.2.1/)

PriceGenerator 2.2.1 поддерживает CPython 3.10–3.15.

```bash
python -m pip install pricegenerator==2.2.1
python -m pip install 'pricegenerator[export]==2.2.1'  # Для экспорта в PNG и JPEG.
```

Чтобы установить пакет из локальной копии репозитория, выполните
`python -m pip install .`.
[Что нового в 2.2.1](https://fuzzy-technologies.com/PriceGenerator/ru/release-2-2/) ·
[Предыдущие выпуски](https://github.com/Fuzzy-Technologies/PriceGenerator/releases)

![PriceGenerator от Fuzzy Technologies. Генератор синтетических рыночных данных.](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-product-card.webp)

## Сгенерировать свечи и записать CSV

```python
from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV

config = GenerationConfig(seed=0, horizon=240, volatility=0.01)
prices = Generate(config)
WriteCSV(prices, "prices.csv", volume_as_count=True)
restored = ReadCSV("prices.csv")
```

Объект `GenerationConfig` после создания изменить нельзя. По умолчанию
используются фиксированное время начала в UTC и модель `regime_v3` с
целочисленным синтетическим счётчиком объёма. Для прежних сценариев с
непрерывным объёмом укажите `model="regime_v2"`.
Параметр `seed` задаёт начальное значение генератора псевдослучайных чисел.
Ноль допустим. У каждого прогона свой ГПСЧ, изолированный от глобального
генератора процесса. В спецификации описаны дрейф, смена режимов,
скачки, тени свечей, объём и поведение цены у границ.
[Как работает модель и чем она отличается от 1.4.93](https://fuzzy-technologies.com/PriceGenerator/ru/scenario-guide/)

Таблица OHLCV содержит шесть столбцов в порядке
`datetime, open, high, low, close, volume`. Метки времени приведены к UTC
и хранятся с наносекундной точностью. Цены и объём — конечные значения
типа `float64`. Если в исходных метках отсутствует смещение, укажите часовой
пояс явно. `ValidateOHLCV` возвращает отдельную таблицу в установленном
формате и позволяет проверить шаг между барами и пропуски.
[Формат OHLCV и CSV](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#csv)

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

Сохраните манифест вместе с CSV. В нём указаны параметры, модель, ГПСЧ, версия
пакета и окружение, а также два контрольных хеша — сценария и самих свечей.
По умолчанию `Replay` проверяет совпадение окружения. Параметр
`strict_environment=False` позволяет повторить прогон в другом окружении
при условии точного совпадения обоих хешей. Версия PriceGenerator должна
совпадать с версией в манифесте. `Analyze` и `Indicators`
рассчитывают показатели отдельно от исходной таблицы и указывают причину,
если расчёт неприменим.
[Руководство по анализу](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#analysis)

Вызов `Chart(prices)` открывает интерактивный HTML-график, который работает
и без интернета. В пакетном скрипте задайте `view=False`. Формат файла
определяется расширением. SVG доступен в базовой установке, для PNG и JPEG
нужен `[export]`. С `analysis=True` на график добавляются индикаторы и сводка.
`DisplayChart(prices)` выводит график прямо в блокноте Jupyter, для которого
при необходимости можно установить `.[notebook]`. Один полупрозрачный
водяной знак расположен на ценовой панели.
[Форматы и настройки графиков](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#charts)

## Те же операции из командной строки

```bash
pricegenerator generate --seed 0 --horizon 240 --output prices.csv --manifest scenario.json
pricegenerator replay scenario.json --output replay.csv
pricegenerator validate prices.csv --timeframe-seconds 3600 --no-gaps
pricegenerator analyze prices.csv --output statistics.json
pricegenerator chart prices.csv --output chart.html --no-view --analysis
```

**Где кнопки индикаторов?** Пересоздайте HTML из того же CSV с флагом
`--analysis` или вызовите `Chart(prices, "chart.html", analysis=True)` в Python.
Откройте HTML в браузере. **Bollinger bands** показывают диапазон вокруг
скользящей средней, **SMA 50 / 200** — две средние, а **Midpoint** — середины
диапазонов свечей. Также доступны HMA, VWMA, PSAR, Alligator и Zig-Zag.
В разделе **Individual series** можно переключать отдельные линии.
Для SMA 200 нужно не менее 200 свечей.

Приблизьте участок колёсиком или рамкой (**Box zoom**). Кнопка **Light theme**
включает светлую тему, а **Export PNG** сохраняет выбранный вид. Под графиком
есть краткая сводка. Полный отчёт раскрывается по кнопке **Detailed statistics**.

![Офлайн-график свечей и объёмов с включёнными полосами Боллинджера и средними за 50 и 200 свечей](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-chart-analysis.webp)

Команды также доступны через `python -m pricegenerator`. Передайте настройки
генерации в JSON через `--config`. Значения, явно указанные в командной
строке, имеют приоритет над соответствующими полями файла. CLI сообщает
об ошибке при неизвестных параметрах, `NaN` и бесконечностях, неоднозначных
метках времени и совпадении путей входных и выходных файлов.

В 2.1 появились команды и Python API для генерации и повторного расчёта
ансамблей Монте-Карло. В CPython 3.13–3.15 можно отдельно подключить нечёткую
оценку рыночного режима.
[Монте-Карло](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#monte-carlo) ·
[Нечёткая диагностика](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#research)

В ветке 2.x изменились класс генератора, методы построения графиков
и параметры командной строки. Для переноса кода с 1.x используйте таблицу
соответствий. Исторические данные для сверки собраны в архиве.
[Переход на 2.1](https://fuzzy-technologies.com/PriceGenerator/ru/migration/) ·
[Изменения API графиков](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#charts) ·
[ADR-0010](https://fuzzy-technologies.com/PriceGenerator/ru/migration/) ·
[Архив 1.x](https://fuzzy-technologies.com/PriceGenerator/ru/migration/)

## Сравнить два ряда свечей

Команда `pricegenerator compare` проверяет шаг баров и сопоставляет
показатели двух рядов OHLCV. В отчёте указаны хеши рядов и результаты
проверки по заданным допускам. В полном примере можно сгенерировать
оба ряда, повторить прогон и сохранить график с квантилями Монте-Карло.
[Сравнение рядов](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#compare) · [Пример эксперимента](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#bundle)

## Разработка и расширения

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
```

Перед изменениями изучите правила проекта, команды проверки, требования
к пакету и архитектурные решения.
В рабочей копии начните с `AGENTS.md`.
[Команды разработчика](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#development) ·
[Сборка пакета](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#packaging) ·
[Проверка модели](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#validation)

Экспериментальные функции калибровки и моделирования доступны через модули
`pricegenerator.calibration`, `pricegenerator.evaluation`,
`pricegenerator.extended_models` и `pricegenerator.registry`. Для каждого
рынка пригодность модели проверяют отдельно. Большие ряды удобно
генерировать и записывать частями через `GenerateChunks` и `WriteCSVChunks`.

[Репозиторий](https://github.com/Fuzzy-Technologies/PriceGenerator) ·
[Задачи](https://github.com/Fuzzy-Technologies/PriceGenerator/issues) ·
[Лицензия Apache-2.0](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.2.1/LICENSE) · [English](https://fuzzy-technologies.com/PriceGenerator/)
