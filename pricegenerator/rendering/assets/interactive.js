/* PriceGenerator's offline adapter. User strings are text, never HTML or code. */
(function (root) {
    "use strict";

    const PRICE = "__pg_price";
    const VOLUME = "__pg_volume";
    const MARKERS = "__pg_markers";

    function SeriesName(series) {
        return "__pg_overlay_" + series.key;
    }

    function NumberText(number, precision) {
        const absolute = Math.abs(number);
        return absolute > 0 && (absolute < 10 ** -precision || absolute >= 1e21) ?
            number.toExponential(Math.min(precision, 6)) : number.toFixed(precision);
    }

    function ScaledText(number, scale, precision, volume = false) {
        const product = number * scale;
        if (!Number.isFinite(product)) return NumberText(number, precision) + " × " + scale.toExponential(2);
        return volume ? String(product) : NumberText(product, precision);
    }

    function Layout(width, height) {
        const left = width < 640 ? 62 : 82;
        const right = 28;
        const top = 112;
        const usable = Math.max(116, height - top - 100);
        const priceHeight = Math.floor(usable * 0.73);
        return {left, right, top, priceHeight, volumeTop: top + priceHeight + 25,
            volumeHeight: Math.max(25, usable - priceHeight - 25), width};
    }

    function BrandingGraphics(branding, layout) {
        const graphics = [{id: "brand-emblem", type: "image", silent: true, z: 6,
            clipPath: {type: "circle", shape: {cx: 43, cy: 38, r: 23}},
            style: {image: branding.emblem, x: 20, y: 15, width: 46, height: 46}}];
        if (layout.width >= 700) {
            graphics.push({id: "brand-wordmark", type: "image", silent: true, z: 6,
                style: {image: branding.watermark || branding.wordmark, x: layout.width - 204, y: 28,
                    width: 174, height: 31.32, opacity: 0.88}});
        }
        const available = layout.width - layout.left - layout.right;
        const count = Math.max(1, Math.floor(available / 220));
        const watermarkWidth = Math.min(174, available - 12);
        [layout.top + layout.priceHeight, layout.volumeTop + layout.volumeHeight].forEach((bottom, panel) => {
            for (let index = 0; index < count; index += 1) {
                graphics.push({id: "watermark-" + panel + "-" + index, type: "image",
                    silent: true, z: 0,
                    style: {image: branding.watermark || branding.wordmark,
                        x: layout.left + ((index + 0.5) * available / count) - watermarkWidth / 2,
                        y: bottom - watermarkWidth * 0.18 - 8,
                        width: watermarkWidth, height: watermarkWidth * 0.18, opacity: 0.16}});
            }
        });
        return graphics;
    }

    function ResponsiveOptions(spec, theme, branding, width, height) {
        const layout = Layout(width, height);
        return {
            title: {text: spec.title, left: 80, top: 21,
                textStyle: {fontSize: 19, fontWeight: 600, color: theme.text,
                    width: Math.max(120, width - (width >= 700 ? 310 : 110)), overflow: "truncate"}},
            grid: [{left: layout.left, right: layout.right, top: layout.top,
                height: layout.priceHeight, backgroundColor: theme.panel, show: true, borderWidth: 0, outerBoundsMode: "none"},
            {left: layout.left, right: layout.right, top: layout.volumeTop,
                height: layout.volumeHeight, backgroundColor: theme.panel, show: true, borderWidth: 0, outerBoundsMode: "none"}],
            graphic: BrandingGraphics(branding, layout),
            legend: {left: layout.left, right: layout.right + 70},
            dataZoom: [{id: "time-slider", left: layout.left, right: layout.right}],
            series: spec.markers.length ? [{id: MARKERS, labelLayout: MarkerLayout(layout)}] : [],
        };
    }

    function MarkerLayout(layout) {
        return (parameters) => ({
            x: Math.min(Math.max(parameters.labelRect.x, layout.left + 4),
                layout.width - layout.right - parameters.labelRect.width - 4),
            y: Math.min(Math.max(parameters.labelRect.y, layout.top + 4),
                layout.top + layout.priceHeight - parameters.labelRect.height - 4),
            align: "left", verticalAlign: "top",
        });
    }

    function TooltipFormatter(spec, labels) {
        const timeIndices = new Map(spec.candles.map((candle, index) => [Date.parse(candle.datetime), index]));
        const markers = new Map();
        spec.markers.forEach((marker) => {
            if (!markers.has(marker.candle_index)) markers.set(marker.candle_index, []);
            markers.get(marker.candle_index).push(marker.text);
        });
        return function (parameters) {
            const entries = Array.isArray(parameters) ? parameters : [parameters];
            if (!entries.length) return "";
            const index = timeIndices.get(entries[0].axisValue);
            if (index === undefined) return "";
            const candle = spec.candles[index];
            const format = (number) => NumberText(Number(number), spec.price_precision);
            const lines = [candle.datetime, "O " + format(candle.open) + "    H " + format(candle.high),
                "L " + format(candle.low) + "    C " + format(candle.close), "Volume " + candle.volume];
            const visible = new Set(entries.map((entry) => entry.seriesName));
            spec.series.forEach((series) => {
                if (visible.has(SeriesName(series)) && series.values[index] !== null) {
                    lines.push(labels[SeriesName(series)] + ": " + format(series.values[index]));
                }
            });
            if (visible.has(MARKERS)) (markers.get(index) || []).forEach((text) => lines.push("Marker: " + text));
            return lines.join("\n");
        };
    }

    function BuildOptions(spec, theme, branding, width, height) {
        if (spec.schema_version !== 1) throw new Error("Unsupported chart schema version");
        const layout = Layout(width, height);
        const responsive = ResponsiveOptions(spec, theme, branding, width, height);
        const timestamps = spec.candles.map((candle) => Date.parse(candle.datetime));
        let interval = Infinity;
        let magnitude = 0;
        let minimumMagnitude = Infinity;
        let volumeMagnitude = 0;
        spec.candles.forEach((candle, index) => {
            if (index) interval = Math.min(interval, timestamps[index] - timestamps[index - 1]);
            magnitude = Math.max(magnitude, Math.abs(candle.low), Math.abs(candle.high));
            [candle.open, candle.close, candle.low, candle.high].forEach((value) => {
                if (value !== 0) minimumMagnitude = Math.min(minimumMagnitude, Math.abs(value));
            });
            volumeMagnitude = Math.max(volumeMagnitude, candle.volume);
        });
        spec.series.forEach((overlay) => overlay.values.forEach((value) => {
            if (value !== null) {
                magnitude = Math.max(magnitude, Math.abs(value));
                if (value !== 0) minimumMagnitude = Math.min(minimumMagnitude, Math.abs(value));
            }
        }));
        if (!Number.isFinite(interval)) interval = 3600000;
        // Extreme finite domains need normalization before ECharts computes differences/ticks.
        const priceScale = magnitude > 1e100 || (magnitude > 0 && magnitude < 1e-100) ? magnitude : 1;
        if (priceScale !== 1 && minimumMagnitude / magnitude < 1e-12) {
            throw new RangeError("Interactive charts cannot preserve this mixed numeric range; rescale prices/overlays or remove extreme outlier series");
        }
        const volumeScale = volumeMagnitude > 1e100 || (volumeMagnitude > 0 && volumeMagnitude < 1e-100) ? volumeMagnitude : 1;
        const firstVisible = spec.candles.length > 5000 ? spec.candles.length - 1000 : 0;
        const initialWindow = {startValue: timestamps[firstVisible] - interval / 2,
            endValue: timestamps[timestamps.length - 1] + interval / 2};
        const labels = Object.create(null);
        labels[PRICE] = "OHLC";
        labels[VOLUME] = "Volume";
        labels[MARKERS] = "Markers";
        const selected = {};
        selected[PRICE] = true;
        selected[VOLUME] = true;
        const series = [{id: PRICE, name: PRICE, type: "candlestick", xAxisIndex: 0, yAxisIndex: 0, progressive: 0,
            encode: {x: 0, y: [1, 2, 3, 4]},
            data: spec.candles.map((candle, index) => [timestamps[index], candle.open / priceScale,
                candle.close / priceScale, candle.low / priceScale, candle.high / priceScale]),
            itemStyle: {color: theme.panel, color0: theme.down, borderColor: theme.up, borderColor0: theme.down},
            emphasis: {itemStyle: {borderWidth: 2}}, barMaxWidth: 20},
        {id: VOLUME, name: VOLUME, type: "bar", xAxisIndex: 1, yAxisIndex: 1, progressive: 0,
            itemStyle: {color: theme.up, opacity: 0.62},
            encode: {x: 0, y: 1},
            data: spec.candles.map((candle, index) => ({value: [timestamps[index], candle.volume / volumeScale],
                itemStyle: {color: candle.close >= candle.open ? theme.up : theme.down, opacity: 0.62}})),
            barMaxWidth: 20}];
        spec.series.forEach((overlay, index) => {
            const name = SeriesName(overlay);
            const color = overlay.color || [theme.accent, theme.secondary, theme.warning, theme.up, theme.down][index % 5];
            labels[name] = overlay.label;
            selected[name] = overlay.visible;
            series.push({id: name, name, type: overlay.kind === "points" ? "scatter" : "line", progressive: 0,
                xAxisIndex: 0, yAxisIndex: 0, encode: {x: 0, y: 1},
                data: overlay.values.map((value, candleIndex) => [timestamps[candleIndex], value === null ? null : value / priceScale]), connectNulls: false,
                showSymbol: false, symbolSize: Math.max(3, overlay.width * 2),
                lineStyle: {color, width: overlay.width, type: overlay.dashed ? "dashed" : "solid"},
                itemStyle: {color}, emphasis: {disabled: true}, z: 4});
        });
        if (spec.markers.length) {
            selected[MARKERS] = true;
            series.push({id: MARKERS, name: MARKERS, type: "scatter", xAxisIndex: 0, yAxisIndex: 0, progressive: 0,
                symbolSize: 5, z: 6, itemStyle: {color: theme.warning}, labelLayout: MarkerLayout(layout),
                data: spec.markers.map((marker) => {
                    const candle = spec.candles[marker.candle_index];
                    const price = marker.position === "above" ? candle.high : marker.position === "below" ?
                        candle.low : candle.high / 2 + candle.low / 2;
                    return {value: [timestamps[marker.candle_index], price / priceScale], itemStyle: {color: marker.color || theme.warning},
                        label: {show: true, formatter: () => marker.text,
                            position: marker.position === "below" ? "bottom" : marker.position === "center" ? "inside" : "top",
                            color: marker.color || theme.warning, fontSize: 11, distance: 5,
                            width: 180, overflow: "truncate"}};
                })});
        }
        const axis = (gridIndex) => ({type: "time", gridIndex,
            min: timestamps[0] - interval / 2, max: timestamps[timestamps.length - 1] + interval / 2,
            axisLine: {lineStyle: {color: theme.grid}}, axisTick: {show: false},
            axisLabel: {show: gridIndex === 1, hideOverlap: true, color: theme.muted, lineHeight: 15, fontSize: 10,
                alignMinLabel: "left", alignMaxLabel: "right",
                formatter: (value) => {
                    const [date, time] = new Date(value).toISOString().split("T");
                    return date + "\n" + time.slice(0, interval < 1000 ? 12 : 8) + " UTC";
                }},
            axisPointer: {show: true, label: {backgroundColor: theme.panel, color: theme.text}},
            splitLine: {show: false}});
        return {
            animation: false, useUTC: true, backgroundColor: theme.background,
            textStyle: {fontFamily: "system-ui, sans-serif", color: theme.text},
            title: responsive.title,
            legend: {show: spec.show_controls, type: "scroll", top: 72, left: layout.left,
                right: layout.right + 70, textStyle: {color: theme.muted}, selected,
                data: series.map((item) => item.name), formatter: (name) => labels[name],
                pageTextStyle: {color: theme.muted}, pageIconColor: theme.accent,
                pageIconInactiveColor: theme.grid},
            toolbox: {show: spec.show_controls, right: layout.right, top: 70,
                iconStyle: {borderColor: theme.muted}, emphasis: {iconStyle: {borderColor: theme.accent}},
                feature: {dataZoom: {yAxisIndex: false, xAxisIndex: [0, 1],
                    title: {zoom: "Box zoom", back: "Previous zoom"}}}},
            grid: responsive.grid,
            xAxis: [axis(0), axis(1)],
            yAxis: [{type: "value", gridIndex: 0, scale: true,
                axisLabel: {color: theme.muted, formatter: (value) => ScaledText(value, priceScale, spec.price_precision)},
                splitLine: {lineStyle: {color: theme.grid}}, axisPointer: {label: {
                    formatter: (parameters) => ScaledText(parameters.value, priceScale, spec.price_precision)}}},
            {type: "value", gridIndex: 1, min: 0, splitNumber: 2,
                axisLabel: {color: theme.muted, formatter: (value) => ScaledText(value, volumeScale, 2, true)}, splitLine: {lineStyle: {color: theme.grid}},
                axisPointer: {label: {formatter: (parameters) => ScaledText(parameters.value, volumeScale, 2, true)}},
                name: "Volume", nameLocation: "middle", nameGap: 48,
                nameTextStyle: {color: theme.muted}}],
            axisPointer: {link: [{xAxisIndex: [0, 1]}], lineStyle: {color: theme.accent, type: "dashed"}},
            tooltip: {trigger: "axis", renderMode: "richText", confine: true,
                backgroundColor: theme.panel, borderColor: theme.grid, textStyle: {color: theme.text},
                axisPointer: {type: "cross", lineStyle: {color: theme.accent}},
                formatter: TooltipFormatter(spec, labels)},
            dataZoom: [{id: "time-inside", type: "inside", xAxisIndex: [0, 1], filterMode: "filter",
                ...initialWindow,
                zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false,
                minValueSpan: spec.candles.length > 1 ? interval : 0},
            {id: "time-slider", type: "slider", xAxisIndex: [0, 1], filterMode: "filter",
                ...initialWindow,
                show: spec.show_controls, bottom: 7, height: 21, left: layout.left, right: layout.right,
                borderColor: theme.grid, backgroundColor: theme.panel, fillerColor: theme.accent + "25",
                handleStyle: {color: theme.accent}, showDetail: false, textStyle: {color: theme.muted}}],
            graphic: responsive.graphic, series,
        };
    }

    function CreateController(chart, spec, theme, branding, container, environment) {
        let disposed = false;
        let boxZoom = false;
        let observer = null;
        const listeners = [];
        const groups = new Map();
        spec.series.forEach((series) => {
            if (series.group !== null) {
                if (!groups.has(series.group)) groups.set(series.group, []);
                groups.get(series.group).push(SeriesName(series));
            }
        });
        function Selected() {
            return chart.getOption().legend[0].selected;
        }
        function Reset() {
            chart.dispatchAction({type: "restore"});
            boxZoom = false;
            chart.dispatchAction({type: "takeGlobalCursor", key: "dataZoomSelect", dataZoomSelectActive: false});
        }
        function SetBoxZoom(active) {
            boxZoom = Boolean(active);
            chart.dispatchAction({type: "takeGlobalCursor", key: "dataZoomSelect", dataZoomSelectActive: boxZoom});
        }
        function FullRange() {
            chart.dispatchAction({type: "dataZoom", start: 0, end: 100});
        }
        function ToggleGroup(group) {
            const members = groups.get(group);
            if (!members) throw new Error("Unknown overlay group");
            const selected = Selected();
            const hide = members.every((name) => selected[name] !== false);
            members.forEach((name) => chart.dispatchAction({type: hide ? "legendUnSelect" : "legendSelect", name}));
        }
        function ExportPNG() {
            return chart.getDataURL({type: "png", pixelRatio: 2, backgroundColor: theme.background,
                excludeComponents: ["toolbox"]});
        }
        function Resize() {
            if (disposed) return;
            chart.resize();
            const width = chart.getWidth();
            const height = chart.getHeight();
            // Preserve zoom and selected legends while replacing only layout-dependent components.
            chart.setOption(ResponsiveOptions(spec, theme, branding, width, height), {replaceMerge: ["graphic"]});
        }
        function Listen(element, type, handler) {
            element.addEventListener(type, handler);
            listeners.push(() => element.removeEventListener(type, handler));
        }
        function Dispose() {
            if (disposed) return;
            disposed = true;
            if (observer) observer.disconnect();
            listeners.forEach((remove) => remove());
            chart.dispose();
        }
        chart.on("globalcursortaken", (event) => {
            boxZoom = event.key === "dataZoomSelect" && Boolean(event.dataZoomSelectActive);
        });
        if (environment.ResizeObserver) {
            observer = new environment.ResizeObserver(Resize);
            observer.observe(container);
        } else {
            Listen(environment, "resize", Resize);
        }
        Listen(environment, "pagehide", Dispose);
        return {Reset, SetBoxZoom, FullRange, ToggleGroup, ExportPNG, Resize, Dispose, Listen, groups, Selected,
            chart, get boxZoom() {return boxZoom;}};
    }

    function LoadBranding(branding, environment) {
        const entries = Object.entries(branding).map(([key, source]) => new Promise((resolve, reject) => {
            const image = new environment.Image();
            image.onload = () => resolve([key, image]);
            image.onerror = () => reject(new Error("A required branding image could not be decoded"));
            image.src = source;
        }));
        return Promise.all(entries).then((loaded) => Object.fromEntries(loaded));
    }

    function TintWatermark(image, theme, environment) {
        const canvas = environment.document.createElement("canvas");
        canvas.width = image.naturalWidth || image.width;
        canvas.height = image.naturalHeight || image.height;
        const context = canvas.getContext("2d");
        context.drawImage(image, 0, 0);
        context.globalCompositeOperation = "source-in";
        context.fillStyle = theme.muted;
        context.fillRect(0, 0, canvas.width, canvas.height);
        return canvas;
    }

    function AttachControls(controller, controls, status, environment) {
        const buttons = controls.querySelectorAll("button[data-action]");
        const actions = {
            pan: () => controller.SetBoxZoom(false),
            box: () => controller.SetBoxZoom(!controller.boxZoom),
            reset: () => controller.Reset(),
            full: () => controller.FullRange(),
            export: () => {
                const link = environment.document.createElement("a");
                link.download = "pricegenerator-chart.png";
                link.href = controller.ExportPNG();
                link.click();
            },
        };
        buttons.forEach((button) => controller.Listen(button, "click", () => {
            try {
                actions[button.dataset.action]();
                status.textContent = button.dataset.action === "export" ? "PNG exported." :
                    controller.boxZoom ? "Drag a rectangle to zoom both panels." : "Drag to pan; use the wheel to zoom.";
                const box = controls.querySelector('[data-action="box"]');
                box.setAttribute("aria-pressed", String(controller.boxZoom));
            } catch (error) {
                status.textContent = "Chart action failed: " + error.message;
            }
        }));
        const groups = controls.querySelector("[data-groups]");
        const groupButtons = new Map();
        controller.groups.forEach((members, name) => {
            const button = environment.document.createElement("button");
            button.type = "button";
            button.textContent = name;
            groupButtons.set(name, button);
            controller.Listen(button, "click", () => {controller.ToggleGroup(name); UpdateGroups();});
            groups.appendChild(button);
        });
        function UpdateGroups() {
            const selected = controller.Selected();
            controller.groups.forEach((members, name) => groupButtons.get(name).setAttribute("aria-pressed",
                String(members.every((member) => selected[member] !== false))));
        }
        controller.chart.on("legendselectchanged", UpdateGroups);
        controller.chart.on("restore", UpdateGroups);
        controller.chart.on("globalcursortaken", () => {
            controls.querySelector('[data-action="box"]').setAttribute("aria-pressed", String(controller.boxZoom));
        });
        UpdateGroups();
    }

    async function Mount(container, spec, theme, branding, controls, status, runtime, environment) {
        const images = await LoadBranding(branding, environment);
        images.watermark = TintWatermark(images.wordmark, theme, environment);
        const chart = runtime.init(container, null, {renderer: "canvas"});
        let controller;
        try {
            chart.setOption(BuildOptions(spec, theme, images, chart.getWidth(), chart.getHeight()));
            controller = CreateController(chart, spec, theme, images, container, environment);
            if (spec.show_controls) AttachControls(controller, controls, status, environment);
            status.textContent = "Ready. Drag to pan; use the wheel to zoom. All timestamps are UTC.";
            return controller;
        } catch (error) {
            if (controller) controller.Dispose();
            else chart.dispose();
            throw error;
        }
    }

    const api = {BuildOptions, CreateController, LoadBranding, TintWatermark, AttachControls, Mount};
    if (typeof module !== "undefined" && module.exports) module.exports = api;
    else root.PriceGeneratorView = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
