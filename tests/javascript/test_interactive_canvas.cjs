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
    "FuzzyTechnologies-Logo-transp.png")).toString("base64"), emblem: "data:image/png;base64," +
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

test("Mount followed immediately by PNG export contains decoded header and all watermarks", async () => {
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
            {name: "wordmark", x: spec.width - 204, y: 28, width: 174, height: 32},
            ...graphics.filter((item) => item.id.startsWith("watermark-")).map((item) => ({name: item.id,
                x: item.style.x, y: item.style.y, width: item.style.width, height: item.style.height}))];
        controller.chart.setOption({graphic: []}, {replaceMerge: ["graphic"]});
        const plain = await harness.DecodePNG(controller.ExportPNG());
        assert.ok(regions.some((region) => region.name.startsWith("watermark-0")));
        assert.ok(regions.some((region) => region.name.startsWith("watermark-1")));
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
        for (const label of labels) {
            const rectangle = label.getBoundingRect().clone();
            const transform = label.getComputedTransform();
            if (transform) rectangle.applyTransform(transform);
            assert.ok(rectangle.x >= 65 && rectangle.x + rectangle.width <= 449,
                "Annotation text must not clip at either price-panel edge");
            assert.ok(rectangle.y >= 115 && rectangle.y + rectangle.height <= 217,
                "Annotation text must remain inside the price panel vertically");
        }
    } finally {
        controller.Dispose();
    }
});
