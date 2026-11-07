/* Mandatory CI raster gate with locked native Canvas; no conditional skips. */
"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const {CreateHarness} = require("../../tools/chart_runtime/canvas_environment.cjs");
const adapter = require("../../pricegenerator/rendering/assets/interactive.js");
const brandRoot = path.resolve(__dirname, "../../pricegenerator/rendering/assets/branding");
const branding = {wordmark: "data:image/png;base64," + readFileSync(path.join(brandRoot,
    "FuzzyTechnologies-Logo-registered.png")).toString("base64"), emblem: "data:image/png;base64," +
    readFileSync(path.join(brandRoot, "ftech-emblem-192.png")).toString("base64")};
const theme = {background: "#080d18", panel: "#111a2b", text: "#e3ecff", muted: "#95a6c6",
    grid: "#26344b", up: "#40e0cf", down: "#ee72d3", accent: "#57c7ff",
    secondary: "#ad8cff", warning: "#ffc46b"};

function Spec(count = 1000) {
    return {schema_version: 1, candles: Array.from({length: count}, (_, index) => ({
        datetime: new Date(Date.UTC(2026, 0, 1) + index * 3600000).toISOString(),
        open: 100 + index % 10, close: 103 + index % 10, low: 98 + index % 10,
        high: 105 + index % 10, volume: 200 + index % 150})),
    title: "Offline Canvas gate", series: [], markers: [], summary: [], theme: "dark",
    width: 960, height: 600, price_precision: 2, show_controls: false};
}

function Differences(first, second, region, ratio = 2) {
    let difference = 0;
    for (let y = Math.floor(region.y * ratio); y < Math.floor((region.y + region.height) * ratio); y += 1) {
        for (let x = Math.floor(region.x * ratio); x < Math.floor((region.x + region.width) * ratio); x += 1) {
            const offset = (y * first.width + x) * 4;
            if (first.pixels[offset] !== second.pixels[offset] || first.pixels[offset + 1] !== second.pixels[offset + 1] ||
                first.pixels[offset + 2] !== second.pixels[offset + 2]) difference += 1;
        }
    }
    return difference;
}

test("Mount followed immediately by PNG export contains decoded emblem and one price-panel wordmark", async () => {
    const harness = CreateHarness();
    const spec = Spec();
    const status = {textContent: ""};
    const controller = await adapter.Mount(harness.Canvas(spec.width, spec.height), spec, theme, branding,
        null, status, harness.runtime, harness.environment);
    try {
        const exported = await harness.DecodePNG(controller.ExportPNG());
        assert.equal(exported.width, spec.width * 2);
        assert.equal(exported.height, spec.height * 2);
        assert.match(status.textContent, /^Ready\./);
        const graphics = controller.chart.getOption().graphic[0].elements;
        const regions = [{name: "emblem", x: 20, y: 15, width: 46, height: 46},
            ...graphics.filter((item) => item.id.startsWith("watermark-")).map((item) => ({name: item.id,
                x: item.style.x, y: item.style.y, width: item.style.width, height: item.style.height}))];
        controller.chart.setOption({graphic: []}, {replaceMerge: ["graphic"]});
        const plain = await harness.DecodePNG(controller.ExportPNG());
        assert.equal(regions.filter((region) => region.name.startsWith("watermark-")).length, 1);
        assert.equal(regions[1].name, "watermark-price");
        assert.equal(regions[1].x, 90);
        assert.equal(regions[1].width, 210);
        for (const region of regions) assert.ok(Differences(exported, plain, region) > 20,
            region.name + " must survive PNG export as actual non-background pixels");
    } finally {
        controller.Dispose();
    }
    assert.equal(harness.events.size, 0);
});

test("100k rows mount through the real engine with an immediately complete 1000-row viewport", async () => {
    const harness = CreateHarness();
    const spec = Spec(100000);
    const controller = await adapter.Mount(harness.Canvas(spec.width, spec.height), spec, theme, branding,
        null, {textContent: ""}, harness.runtime, harness.environment);
    try {
        assert.equal(controller.chart.getOption().series[0].data.length, 100000);
        assert.equal(controller.chart.getModel().getSeriesByIndex(0).getData().count(), 1000);
        assert.equal(controller.chart.getModel().getSeriesByIndex(1).getData().count(), 1000);
        const output = await harness.DecodePNG(controller.ExportPNG());
        assert.equal(output.width, 1920);
        const chartPixels = output.pixels.filter((value, index) => index % 4 !== 3 && value > 100).length;
        assert.ok(chartPixels > 10000, "The exported chart must contain real rendered chart content");
        controller.chart.dispatchAction({type: "dataZoom", start: 98, end: 99});
        const timestamp = Date.parse(spec.candles[98500].datetime);
        assert.equal(controller.chart.convertToPixel({xAxisIndex: 0}, timestamp),
            controller.chart.convertToPixel({xAxisIndex: 1}, timestamp));
    } finally {
        controller.Dispose();
    }
});

test("long text exports and edge annotations stay within the price panel", async () => {
    const harness = CreateHarness();
    const spec = Spec(10);
    spec.width = 480;
    spec.height = 360;
    spec.title = "Long title ".repeat(30);
    spec.markers = [
        {candle_index: 0, text: "First-candle annotation", position: "below", color: null},
        {candle_index: 5, text: "Centered label", position: "center", color: null},
        {candle_index: 9, text: "Trailing marker annotation ".repeat(15), position: "above", color: null},
    ];
    const controller = await adapter.Mount(harness.Canvas(spec.width, spec.height), spec, theme, branding,
        null, {textContent: ""}, harness.runtime, harness.environment);
    try {
        const output = await harness.DecodePNG(controller.ExportPNG());
        assert.equal(output.width, 960);
        const labels = controller.chart.getZr().storage.getDisplayList().filter((item) =>
            item.type === "tspan" && item.style.fill === theme.warning);
        assert.ok(labels.length >= 3, "Every annotation must render a visible label");
        const {top, height} = controller.chart.getOption().grid[0];
        for (const label of labels) {
            const rectangle = label.getBoundingRect().clone();
            const transform = label.getComputedTransform();
            if (transform) rectangle.applyTransform(transform);
            assert.ok(rectangle.x >= 65 && rectangle.x + rectangle.width <= 449,
                "Annotation text must not clip at either price-panel edge");
            assert.ok(rectangle.y >= top && rectangle.y + rectangle.height <= top + height,
                "Annotation text must remain inside the price panel vertically");
        }
    } finally {
        controller.Dispose();
    }
});

test("PNG keeps the zoomed candles and volume without the interactive slider", async () => {
    const harness = CreateHarness();
    const spec = {...Spec(120), show_controls: true};
    const images = await adapter.LoadBranding(branding, harness.environment);
    images.watermark = adapter.TintWatermark(images.wordmark, theme, harness.environment);
    const canvas = harness.Canvas(spec.width, spec.height);
    const chart = harness.runtime.init(canvas, null, {renderer: "canvas"});
    chart.setOption(adapter.BuildOptions(spec, theme, images, spec.width, spec.height));
    const controller = adapter.CreateController(chart, spec, theme, images, canvas, harness.environment);
    try {
        chart.dispatchAction({type: "dataZoom", start: 20, end: 65});
        const zoom = chart.getOption().dataZoom[0];
        const snapshot = () => chart.getDataURL({type: "png", pixelRatio: 2, backgroundColor: theme.background});
        const before = await harness.DecodePNG(snapshot());
        const exported = await harness.DecodePNG(controller.ExportPNG());
        const after = await harness.DecodePNG(snapshot());
        const slider = {x: 82, y: 572, width: 850, height: 21};
        const [price, volume] = chart.getOption().grid.map(({left, right, top, height}) =>
            ({x: left, y: top, width: spec.width - left - right, height}));
        assert.ok(Differences(before, exported, slider) > 1000, "Export must omit the rendered slider");
        assert.equal(Differences(before, after, slider), 0, "The live slider must remain visible");
        assert.equal(Differences(before, exported, price), 0, "Export must preserve zoomed price pixels");
        assert.equal(Differences(before, exported, volume), 0, "Export must preserve zoomed volume pixels");
        assert.equal(chart.getOption().dataZoom[0].startValue, zoom.startValue);
        assert.equal(chart.getOption().dataZoom[0].endValue, zoom.endValue);
    } finally {
        controller.Dispose();
    }
});

test("theme switching keeps the zoom and selected indicators and redraws export colors", async () => {
    const harness = CreateHarness();
    const spec = Spec(30);
    spec.series = [{key: "midpoint-points", label: "High/low midpoint points", group: "Midpoint",
        kind: "points", visible: false, color: null, values: spec.candles.map((candle) => (candle.high + candle.low) / 2),
        width: 1.8, dashed: false}];
    const canvas = harness.Canvas(spec.width, spec.height);
    const controller = await adapter.Mount(canvas, spec, theme, branding,
        null, {textContent: ""}, harness.runtime, harness.environment);
    try {
        const initial = controller.chart.getOption().dataZoom[0];
        controller.chart.dispatchAction({type: "dataZoom", start: 25, end: 75});
        const zoom = controller.chart.getOption().dataZoom[0];
        controller.ToggleGroup("Midpoint");
        const light = {...theme, background: "#f5f7fc", panel: "#ffffff", text: "#182338"};
        controller.SetTheme(light);
        const options = controller.chart.getOption();
        assert.equal(options.backgroundColor, light.background);
        assert.equal(options.series[2].itemStyle.color, light.text);
        assert.equal(options.series[2].symbolSize, 6);
        assert.equal(options.dataZoom[0].startValue, zoom.startValue);
        assert.equal(options.dataZoom[0].endValue, zoom.endValue);
        assert.equal(controller.Selected()["__pg_overlay_midpoint-points"], true);
        const exported = await harness.DecodePNG(controller.ExportPNG());
        assert.deepEqual(Array.from(exported.pixels.slice(0, 4)), [245, 247, 252, 255]);
        assert.equal(controller.PreviousZoom(), true);
        assert.equal(controller.chart.getOption().dataZoom[0].startValue, initial.startValue);
        controller.Reset();
        assert.equal(controller.Selected()["__pg_overlay_midpoint-points"], false);
        assert.equal(controller.chart.getOption().backgroundColor, light.background);
    } finally {
        controller.Dispose();
    }
});
