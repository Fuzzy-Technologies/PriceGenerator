---
layout: default
lang: ru
route: release-2-1
title: "Предварительная версия PriceGenerator 2.1"
permalink: /ru/release-2-1/
redirect_from:
  - /docs/site/content/ru/release-2-1.html
---
# Предварительная версия PriceGenerator 2.1
{: id="pricegenerator-21-предварительный-выпуск" }

В версии 2.1 один сценарий впервые можно было разыграть много раз и посмотреть, как разойдутся траектории цены. Каждый ряд можно получить повторно, а на общем графике видно, в каких пределах оказывались цены закрытия к выбранному часу.

- По каждой траектории рассчитывается максимальная просадка цены. Для сравнения траекторий доступны квантили.
- Дополнение FuzzyRoutines оценивает состояние рынка по методу Мамдани и показывает, какие правила повлияли на оценку.
- Запись CSV ускорилась, а при экспорте графиков требуется меньше памяти.
- В примере с BTC/USD параметры подбираются по одному месяцу и проверяются по следующему. [Как проходила проверка на данных Bitstamp](https://fuzzy-technologies.com/PriceGenerator/ru/experiments/#bitstamp)

[Скачать архив версии 2.1 на GitHub](https://github.com/Fuzzy-Technologies/PriceGenerator/releases/tag/v2.1.0) · [Перенести прежние скрипты](https://fuzzy-technologies.com/PriceGenerator/ru/migration/) · [Что нового в 2.2.1](https://fuzzy-technologies.com/PriceGenerator/ru/release-2-2/)

[English](../en/release-2-1.md) · [简体中文](../zh-CN/release-2-1.md)
