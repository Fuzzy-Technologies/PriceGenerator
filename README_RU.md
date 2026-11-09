# PriceGenerator

![PriceGenerator от Fuzzy Technologies. Генератор синтетических рыночных данных.](docs/assets/pricegenerator-product-card.webp)

[Руководство](docs/site/content/ru/scenario-guide.md) ·
[English](docs/site/content/en/scenario-guide.md) ·
[简体中文](docs/site/content/zh-CN/scenario-guide.md) ·
[Что нового в 2.2](docs/release-2-2-ru.md)

PriceGenerator строит синтетические ряды свечей OHLCV для тестирования
торговых систем и количественных экспериментов. Можно задать параметры
рынка, сохранить свечи в CSV, повторить прогон и посмотреть результат
на графике. Для оценки прогнозов и доходности стратегии нужна отдельная
проверка на рыночных данных.

## Установка

PriceGenerator 2.2 поддерживает CPython 3.10–3.15.

```bash
python -m pip install pricegenerator==2.2.0
python -m pip install 'pricegenerator[export]==2.2.0'  # Для экспорта в PNG и JPEG.
```

Чтобы установить пакет из локальной копии репозитория, выполните
`python -m pip install .`.
[Что нового в 2.2](docs/release-2-2-ru.md) ·
[Предыдущие выпуски](https://github.com/Fuzzy-Technologies/PriceGenerator/releases)

## Сгенерировать свечи и записать CSV

```python
from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV

config = GenerationConfig(seed=0, horizon=240, volatility=0.01)
prices = Generate(config)
WriteCSV(prices, "prices.csv")
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
[Как работает модель и чем она отличается от 1.4.93](docs/model-regime-v2.md)

Таблица OHLCV содержит шесть столбцов в порядке
`datetime, open, high, low, close, volume`. Метки времени приведены к UTC
и хранятся с наносекундной точностью. Цены и объём — конечные значения
типа `float64`. Если в исходных метках отсутствует смещение, укажите часовой
пояс явно. `ValidateOHLCV` возвращает отдельную таблицу в установленном
формате и позволяет проверить шаг между барами и пропуски.
[Формат OHLCV и CSV](docs/data-contract.md)

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
[Руководство по анализу](docs/analysis.md)

Вызов `Chart(prices)` открывает интерактивный HTML-график, который работает
и без интернета. В пакетном скрипте задайте `view=False`. Формат файла
определяется расширением. SVG доступен в базовой установке, для PNG и JPEG
нужен `[export]`. С `analysis=True` на график добавляются индикаторы и сводка.
`DisplayChart(prices)` выводит график прямо в блокноте Jupyter, для которого
при необходимости можно установить `.[notebook]`. Один полупрозрачный
водяной знак расположен на ценовой панели.
[Форматы и настройки графиков](docs/chart-migration.md)

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

![Офлайн-график свечей и объёмов с включёнными полосами Боллинджера и средними за 50 и 200 свечей](https://raw.githubusercontent.com/Fuzzy-Technologies/PriceGenerator/master/docs/assets/pricegenerator-chart-analysis.webp)

Команды также доступны через `python -m pricegenerator`. Передайте настройки
генерации в JSON через `--config`. Значения, явно указанные в командной
строке, имеют приоритет над соответствующими полями файла. CLI сообщает
об ошибке при неизвестных параметрах, `NaN` и бесконечностях, неоднозначных
метках времени и совпадении путей входных и выходных файлов.

В 2.1 появились команды и Python API для генерации и повторного расчёта
ансамблей Монте-Карло. В CPython 3.13–3.15 можно отдельно подключить нечёткую
оценку рыночного режима.
[Монте-Карло](docs/monte-carlo.md) ·
[Нечёткая диагностика](docs/fuzzy-diagnostics.md)

В ветке 2.x изменились класс генератора, методы построения графиков
и параметры командной строки. Для переноса кода с 1.x используйте таблицу
соответствий. Исторические данные для сверки собраны в архиве.
[Переход на 2.1](docs/site/content/ru/migrate-to-2-1.md) ·
[Изменения API графиков](docs/chart-migration.md) ·
[ADR-0010](docs/adr/0010-modern-only-public-api.md) ·
[Архив 1.x](docs/baseline/README.md)

## Сравнить два ряда свечей

Команда `pricegenerator compare` проверяет шаг баров и сопоставляет
показатели двух рядов OHLCV. В отчёте указаны хеши рядов и результаты
проверки по заданным допускам. В полном примере можно сгенерировать
оба ряда, повторить прогон и сохранить график с квантилями Монте-Карло.
[Сравнение рядов](docs/reference-comparison.md) · [Пример эксперимента](docs/examples/experiment-bundle.md)

## Разработка и расширения

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
```

Перед изменениями изучите правила проекта, команды проверки, требования
к пакету и архитектурные решения.
[AGENTS.md](AGENTS.md) ·
[Команды разработчика](docs/development.md) ·
[Сборка пакета](docs/packaging.md) ·
[Архитектурные решения](docs/adr/README.md)

Экспериментальные функции калибровки и моделирования доступны через модули
`pricegenerator.calibration`, `pricegenerator.evaluation`,
`pricegenerator.extended_models` и `pricegenerator.registry`. Для каждого
рынка пригодность модели проверяют отдельно. Большие ряды удобно
генерировать и записывать частями через `GenerateChunks` и `WriteCSVChunks`.

[Репозиторий](https://github.com/Fuzzy-Technologies/PriceGenerator) ·
[Задачи](https://github.com/Fuzzy-Technologies/PriceGenerator/issues) ·
[Лицензия Apache-2.0](LICENSE) · [English](README.md)
