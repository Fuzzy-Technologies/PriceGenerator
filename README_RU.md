# PriceGenerator

Воспроизводимые синтетические OHLCV-сценарии для тестирования торговых систем
и количественных исследований. API v2 разделяет генерацию, проверку данных,
диагностику, CSV, воспроизведение и графики. Это тестовые данные: генератор
не прогнозирует рынок и не подтверждает прибыльность торговой стратегии.

## Установка

Поддерживаемое окно версий — CPython 3.10–3.13. После публикации версии 2.0.0
на PyPI установите именно этот выпуск:

```bash
python -m pip install 'pricegenerator==2.0.0'
python -m pip install 'pricegenerator[export]==2.0.0'  # Optional PNG/JPEG.
```

Для исходного дерева используйте `python -m pip install .` или
`python -m pip install '.[export]'`. Подготовка релиза сама по себе не загружает
файлы: проверяйте [порядок выпуска](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/releasing.md) и фактическую страницу PyPI,
прежде чем считать публикацию завершённой. Ссылки ведут на тег v2.0.0.

## Генерация и CSV

```python
from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV

config = GenerationConfig(seed=0, horizon=240, volatility=0.01)
prices = Generate(config)
WriteCSV(prices, "prices.csv")
restored = ReadCSV("prices.csv")
```

`GenerationConfig` неизменяем. По умолчанию заданы фиксированное начало UTC
и версионируемая модель `regime_v2`; seed 0 допустим. Генерация использует свой
RNG и не изменяет глобальное состояние случайных чисел. [Описание модели](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/model-regime-v2.md)
определяет дрейф, режимы, независимые шоки/тени, объём, отражение и границы.

Канонические столбцы: `datetime, open, high, low, close, volume`. Время — UTC
с наносекундной точностью, числа — конечные float64. Для импортируемого времени
без часового пояса его нужно указать явно. `ValidateOHLCV` возвращает отдельные
канонические данные и проверяет заданный шаг/пропуски. Корректность структуры
сама по себе не доказывает соответствие реальному рынку.

## Воспроизведение, диагностика и график

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

Манифест хранит полную конфигурацию, модель, RNG, версию библиотеки, окружение
и отдельные отпечатки идентичности сценария и канонических данных. Replay требует совпадения
окружения; `strict_environment=False` всё равно требует точного совпадения
обоих отпечатков. Диагностика и индикаторы не изменяют исходную таблицу. Отсутствующие
или неприменимые оценки сопровождаются причиной.

`Chart(prices)` создаёт автономный интерактивный HTML и открывает браузер.
Для пакетной работы задавайте `view=False`. SVG требует явного пути `.svg`,
а PNG/JPEG — также зависимости `[export]`. `analysis=True` явно добавляет
индикаторы и диагностику. `DisplayChart(prices)` встраивает HTML в notebook;
если в окружении нет нужных инструментов, установите `.[notebook]`. На ценовой
панели размещён один полупрозрачный фирменный водяной знак.
Подробнее: [руководство по графикам](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/chart-migration.md).

## Командная строка

```bash
pricegenerator generate --seed 0 --horizon 240 --output prices.csv --manifest scenario.json
pricegenerator replay scenario.json --output replay.csv
pricegenerator validate prices.csv --timeframe-seconds 3600 --no-gaps
pricegenerator analyze prices.csv --output statistics.json
pricegenerator chart prices.csv --output chart.html --no-view --analysis
```

`python -m pricegenerator` предоставляет те же команды. JSON-файл `--config`
задаёт все параметры генерации; явно заданные общие флаги переопределяют поля.
Неизвестные поля, неконечные числа, неоднозначное время и совпадающие входные/
выходные пути отклоняются. Старый изменяемый класс, методы рисования и флаги
удалены намеренно: см. [миграцию](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/chart-migration.md) и
[ADR-0010](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/adr/0010-modern-only-public-api.md). Исторические результаты
сохранены в [архиве](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/baseline/README.md).

## Разработка и расширения

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
```

Начните с [команд разработки](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/development.md), [упаковки](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/packaging.md)
и [ADR](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/adr/README.md). **AI-участникам: перед изменениями прочитайте
[AGENTS.md](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/AGENTS.md)**, затем связанный протокол и требования к стилю.
Исследовательские функции остаются экспериментальными и вызываются из модулей
`pricegenerator.calibration`, `pricegenerator.evaluation`,
`pricegenerator.extended_models`, `pricegenerator.registry`. Они не входят
в компактный корневой API и не означают проверку на всех реальных рынках.
Для больших данных доступны `GenerateChunks` и `WriteCSVChunks`.

[Репозиторий](https://github.com/Fuzzy-Technologies/PriceGenerator) ·
[Задачи](https://github.com/Fuzzy-Technologies/PriceGenerator/issues) ·
[Лицензия Apache-2.0](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/LICENSE) · [English](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/README.md)
