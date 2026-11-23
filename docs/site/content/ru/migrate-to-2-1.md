---
layout: default
lang: ru
route: migration
title: "Как перенести скрипты с прежних версий"
permalink: /ru/migration/
redirect_from:
  - /docs/site/content/ru/migrate-to-2-1.html
---
# Как перенести скрипты с прежних версий
{: id="переход-на-pricegenerator-21" }

В 1.4.93 у генератора были другие настройки и команды. Для точного повторения старого эксперимента сохраните его окружение, входные файлы и результаты. Для нового проекта начните с [установки 2.2.1](https://fuzzy-technologies.com/PriceGenerator/ru/quick-start/).

| Версия   | Когда она понадобится                                                                                                    |
| -------- | ------------------------------------------------------------------------------------------------------------------------ |
| `1.4.93` | Для воспроизведения результатов, полученных с API 1.x. Версия сохранилась на PyPI.                                       |
| `v2.0.0` | Для воспроизведения первых примеров 2.x. Тег на GitHub соответствует коммиту `83b1b75a99be06947a93314d6c2509a257ed6b3e`. |
| `v2.1.0` | Для экспериментов с предварительной версией. В ней появились метод Монте-Карло и нечёткая диагностика.                   |

## Если ваш проект на 1.4.93

Создайте отдельное окружение CPython 3.10–3.15 для текущей версии. В Python создайте `GenerationConfig` и вызовите `Generate(config)`. В командной строке для генерации служит подкоманда `generate`. Прежний `seed` сам по себе не воспроизведёт свечи из 1.x, поскольку изменился алгоритм. Для нового ряда сохраните манифест.

Чтобы открыть старые данные командами `validate` и `chart`, приведите CSV к формату `datetime,open,high,low,close,volume` и переведите время в UTC. [Формат CSV](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#csv) · [Настройки графиков](https://fuzzy-technologies.com/PriceGenerator/ru/reference/#charts)

## Если вы работали с тестовой версией 2.0
{: id="если-вы-уже-пользовались-тестовой-версией-20" }

Сохраните манифесты 2.0 вместе с версией пакета и зависимостей. При переносе сгенерируйте котировки по тем же исходным параметрам и сравните контрольные суммы OHLCV. Файлы графиков проверяйте отдельно. Для SVG и интерактивного HTML достаточно базового пакета. Для прямого экспорта в PNG и JPEG установите дополнение `export`. Чтобы скрипт не открывал браузер, передайте `--no-view` в командной строке или `view=False` в Python. [Устройство модели](https://fuzzy-technologies.com/PriceGenerator/ru/scenario-guide/)

## Как проверить перенос
{: id="контрольный-прогон-с-фиксированным-seed" }

Выполните команды в новом каталоге. Для проверки исторической версии 2.1 возьмите [архив предварительного выпуска](https://fuzzy-technologies.com/PriceGenerator/ru/release-2-1/). Те же команды работают с установленной версией 2.2.1.

```sh
python -I -m pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 60 --output prices.csv --manifest scenario.json
python -I -m pricegenerator validate prices.csv --timeframe-seconds 60 --no-gaps
python -I -m pricegenerator replay scenario.json --output replay.csv
python -I -m pricegenerator chart prices.csv --output chart.html --analysis --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

В отчёте проверки должно быть 240 строк с минутным интервалом. В одном и том же окружении файлы `prices.csv` и `replay.csv` должны совпасть побайтно. Откройте `chart.html` и выберите **Bollinger bands**. Переключатели индикаторов добавляет флаг `--analysis`. В Python ему соответствует `analysis=True`. [Как выглядят команды и результат в версии 2.0 (GIF)](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-cli-demo.gif)

[English](../en/migrate-to-2-1.md) · [简体中文](../zh-CN/migrate-to-2-1.md)
