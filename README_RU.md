# PriceGenerator

![PriceGenerator от Fuzzy Technologies. Генератор синтетических рыночных данных.](docs/assets/pricegenerator-product-card.webp)

[Руководство](docs/site/content/ru/scenario-guide.md) ·
[English](docs/site/content/en/scenario-guide.md) ·
[简体中文](docs/site/content/zh-CN/scenario-guide.md) ·
[Что нового в 2.1](docs/site/content/ru/release-2-1.md)

PriceGenerator строит синтетические ряды свечей OHLCV для тестирования
торговых систем и количественных экспериментов. Можно задать параметры
рынка, сохранить свечи в CSV, повторить прогон и посмотреть результат
на графике. Для оценки прогнозов и доходности стратегии нужна отдельная
проверка на рыночных данных.

## Установка

Для ветки 2.x нужен CPython 3.10–3.15. На PyPI пока доступна версия 1.4.93.
Версии 2.0.0 и 2.1.0 распространяются как предрелизы на GitHub. Первый
выпуск ветки 2.x на PyPI запланирован на 2.2.0.
[Релизы GitHub](https://github.com/Fuzzy-Technologies/PriceGenerator/releases) ·
[Порядок выпуска](docs/releasing.md)

Из каталога с исходным кодом установите базовый пакет. Для экспорта графиков
в PNG и JPEG используйте вариант с `[export]`.

```bash
python -m pip install .
python -m pip install '.[export]'
```

## Сгенерировать свечи и записать CSV

```python
from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV

config = GenerationConfig(seed=0, horizon=240, volatility=0.01)
prices = Generate(config)
WriteCSV(prices, "prices.csv")
restored = ReadCSV("prices.csv")
```

Объект `GenerationConfig` после создания изменить нельзя. По умолчанию
используются фиксированное время начала в UTC и модель `regime_v2`.
Параметр `seed` задаёт начальное значение генератора псевдослучайных чисел.
Ноль допустим. У каждого прогона свой ГПСЧ, изолированный от глобального
генератора процесса. В спецификации описаны дрейф, смена режимов,
скачки, тени свечей, объём и поведение цены у границ.
[Модель `regime_v2`](docs/model-regime-v2.md)

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
chart_path = Chart(prices, "chart.html", view=False)
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
