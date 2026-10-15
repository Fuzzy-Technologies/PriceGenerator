/* Execute the actual vendored ECharts model plus a deterministic drawing surface. */
"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");
const adapter = require(path.join(root, "pricegenerator/rendering/assets/interactive.js"));
// Keep the runtime and options in one realm: ECharts uses instanceof Array.
// Suppress animation timers only; the actual model/layout/draw path still runs.
const runtime = Function("setTimeout", "clearTimeout", readFileSync(path.join(root,
    "pricegenerator/rendering/assets/echarts/echarts-financial.min.js"), "utf8") +
    ";return PriceGeneratorCharts;")(() => 0, () => {});
const theme = {background: "#080d18", panel: "#111a2b", text: "#e3ecff", muted: "#95a6c6",
    grid: "#26344b", up: "#40e0cf", down: "#ee72d3", accent: "#57c7ff",
    secondary: "#ad8cff", warning: "#ffc46b"};
const branding = {wordmark: {width: 1000, height: 180}, emblem: {width: 192, height: 192}};

function Canvas(width = 1280, height = 760) {
    const canvas = {width, height, nodeName: "CANVAS", style: {},
        setAttribute() {}, addEventListener() {}, removeEventListener() {},
        toDataURL() {return "data:image/png;base64,dGVzdA==";}};
    const context = new Proxy({canvas,
        measureText(text) {return {width: String(text).length * 6};},
        createLinearGradient() {return {addColorStop() {}};},
        createRadialGradient() {return {addColorStop() {}};},
        createPattern() {return {};},
        getImageData() {return {data: new Uint8ClampedArray(4)};}},
    {get(target, key) {return key in target ? target[key] : () => {};}});
    canvas.getContext = () => context;
    return canvas;
}
runtime.setPlatformAPI({createCanvas: Canvas});

function Spec(count = 3) {
    const start = Date.UTC(2026, 0, 1);
    return {schema_version: 1, candles: Array.from({length: count}, (_, index) => ({
        datetime: new Date(start + index * 3600000).toISOString(),
        open: 100 + index % 9, close: 102 + index % 9, high: 105 + index % 9,
        low: 98 + index % 9, volume: 20 + index % 5})),
    title: "Safe chart", series: [{key: "sma", label: "SMA", values: Array.from({length: count},
        (_, index) => index === 0 ? null : 101 + index % 9), color: null, kind: "line",
        visible: false, group: "Trend", width: 1.8, dashed: false}],
    markers: [{candle_index: 1, text: "Signal", position: "above", color: null}],
    summary: [], theme: "dark", width: 1280, height: 760, price_precision: 2, show_controls: true};
}

function NewChart(spec = Spec()) {
    const chart = runtime.init(Canvas(), null, {renderer: "canvas", ssr: true, width: 1280, height: 760});
    chart.setOption(adapter.BuildOptions(spec, theme, branding, 1280, 760));
    return chart;
}

function Environment() {
    const events = new Map();
    const environment = {events, disconnected: false,
        addEventListener(name, handler) {events.set(name, handler);},
        removeEventListener(name) {events.delete(name);}};
    environment.ResizeObserver = class {
        constructor(callback) {environment.resize = callback;}
        observe(container) {environment.observed = container;}
        disconnect() {environment.disconnected = true;}
    };
    return environment;
}

test("real ECharts accepts the complete options and correct OHLC order", () => {
    assert.equal(runtime.version, "6.1.0");
    const chart = NewChart();
    const model = chart.getModel();
    const candle = model.getSeriesByIndex(0).getData();
    assert.equal(candle.count(), 3);
    assert.deepEqual(Array.from(candle.getValues([1, 2, 3, 4], 0)), [100, 102, 98, 105]);
    assert.equal(chart.getOption().animation, false);
    assert.equal(chart.getOption().series[0].itemStyle.color, theme.panel);
    assert.equal(chart.getOption().series[0].itemStyle.color0, theme.down);
    assert.ok(chart.getOption().series.every((series) => series.progressive === 0));
    assert.equal(chart.getOption().legend[0].selected.__pg_overlay_sma, false);
    chart.dispose();
});

test("time gaps and candle-volume pixel positions survive zoom", () => {
    const spec = Spec();
    spec.candles[2].datetime = "2026-01-02T01:00:00.000Z";
    const chart = NewChart(spec);
    const positions = spec.candles.map((candle) => chart.convertToPixel({xAxisIndex: 0}, Date.parse(candle.datetime)));
    assert.ok(Math.abs((positions[2] - positions[1]) / (positions[1] - positions[0]) - 24) < 1e-9);
    chart.dispatchAction({type: "dataZoom", start: 10, end: 80});
    for (const candle of spec.candles) {
        const time = Date.parse(candle.datetime);
        assert.equal(chart.convertToPixel({xAxisIndex: 0}, time), chart.convertToPixel({xAxisIndex: 1}, time));
    }
    chart.dispose();
});

test("uneven millisecond and daily gaps cannot shrink the volume panel independently", () => {
    const spec = Spec();
    spec.candles[0].datetime = "2026-10-15T00:00:00.000Z";
    spec.candles[1].datetime = "2026-10-15T00:00:00.001Z";
    spec.candles[2].datetime = "2026-10-16T00:00:00.000Z";
    const chart = NewChart(spec);
    for (const candle of spec.candles) {
        const value = Date.parse(candle.datetime);
        assert.equal(chart.convertToPixel({xAxisIndex: 0}, value), chart.convertToPixel({xAxisIndex: 1}, value));
    }
    const grids = chart.getModel();
    assert.equal(grids.getComponent("grid", 0).coordinateSystem.getRect().width,
        grids.getComponent("grid", 1).coordinateSystem.getRect().width);
    chart.dispose();
});

test("a 100k snapshot retains every row and initially renders its latest 1000", () => {
    const spec = Spec(100000);
    spec.series = [];
    spec.markers = [];
    const chart = NewChart(spec);
    assert.equal(chart.getOption().series[0].data.length, 100000);
    assert.equal(chart.getModel().getSeriesByIndex(0).getData().count(), 1000);
    assert.equal(chart.getModel().getSeriesByIndex(1).getData().count(), 1000);
    chart.dispatchAction({type: "dataZoom", start: 0, end: 100});
    assert.equal(chart.getModel().getSeriesByIndex(0).getData().count(), 100000);
    chart.dispatchAction({type: "restore"});
    assert.equal(chart.getModel().getSeriesByIndex(0).getData().count(), 1000);
    chart.dispose();
});

test("controller calls real zoom/reset/group actions and cleans event handlers", () => {
    const spec = Spec(50);
    const chart = NewChart(spec);
    const environment = Environment();
    const controller = adapter.CreateController(chart, spec, theme, branding, {}, environment);
    controller.ToggleGroup("Trend");
    assert.equal(controller.Selected().__pg_overlay_sma, true);
    controller.ToggleGroup("Trend");
    assert.equal(controller.Selected().__pg_overlay_sma, false);
    controller.SetBoxZoom(true);
    assert.equal(controller.boxZoom, true);
    chart.dispatchAction({type: "dataZoom", start: 30, end: 60});
    controller.FullRange();
    assert.equal(chart.getModel().getSeriesByIndex(0).getData().count(), 50);
    controller.Reset();
    assert.equal(controller.boxZoom, false);
    assert.equal(controller.Selected().__pg_overlay_sma, false);
    assert.match(controller.ExportPNG(), /^data:image\/png/);
    assert.throws(() => controller.ToggleGroup("missing"), /Unknown/);
    controller.Dispose();
    controller.Dispose();
    assert.equal(environment.disconnected, true);
    assert.equal(environment.events.size, 0);
    assert.equal(chart.isDisposed(), true);
});

test("responsive layout preserves zoom and selected overlays", () => {
    const spec = Spec(40);
    const chart = NewChart(spec);
    const controller = adapter.CreateController(chart, spec, theme, branding, {}, Environment());
    controller.ToggleGroup("Trend");
    chart.dispatchAction({type: "dataZoom", start: 20, end: 70});
    const before = chart.getOption().dataZoom[0];
    chart.resize({width: 480, height: 600});
    controller.Resize();
    const after = chart.getOption().dataZoom[0];
    assert.equal(after.start, before.start);
    assert.equal(after.end, before.end);
    assert.equal(controller.Selected().__pg_overlay_sma, true);
    const graphics = chart.getOption().graphic[0].elements;
    assert.ok(graphics.some((element) => element.id === "brand-emblem"));
    assert.ok(!graphics.some((element) => element.id === "brand-wordmark"));
    assert.ok(graphics.some((element) => element.id.startsWith("watermark-0")));
    assert.ok(graphics.some((element) => element.id.startsWith("watermark-1")));
    controller.Dispose();
});

test("missing overlays and annotation positions preserve their data semantics", () => {
    const spec = Spec();
    spec.markers = ["above", "center", "below"].map((position) => ({candle_index: 0, text: position,
        position, color: null}));
    const options = adapter.BuildOptions(spec, theme, branding, 1280, 760);
    assert.equal(options.series[2].data[0][1], null);
    assert.equal(options.series[2].connectNulls, false);
    assert.deepEqual(options.series[3].data.map((marker) => marker.value[1]), [105, 101.5, 98]);
    assert.equal(options.series[3].data[1].label.position, "inside");
    assert.equal(options.tooltip.renderMode, "richText");
    const tooltip = options.tooltip.formatter([{axisValue: Date.parse(spec.candles[1].datetime), seriesName: "__pg_overlay_sma"}]);
    assert.match(tooltip, /O 101\.00/);
    assert.match(tooltip, /SMA: 102\.00/);
});

test("extreme finite prices and volumes have finite real engine geometry", () => {
    const spec = Spec();
    spec.candles = spec.candles.map((candle) => ({...candle,
        open: -5e307, close: 5e307, low: -1e308, high: 1e308, volume: 1e308}));
    spec.series = [];
    const chart = NewChart(spec);
    const geometry = chart.getModel().getSeriesByIndex(0).getData().getItemLayout(0);
    assert.ok(geometry.ends.every((point) => point.every(Number.isFinite)));
    const options = chart.getOption();
    assert.equal(options.yAxis[0].axisLabel.formatter(1), "1.00e+308");
    assert.equal(options.yAxis[0].axisPointer.label.formatter({value: -1}), "-1.00e+308");
    chart.dispose();
});

test("branding resolves only after both images decode and failures reject", async () => {
    const images = [];
    const environment = {Image: class {constructor() {images.push(this);}}};
    let settled = false;
    const loading = adapter.LoadBranding({wordmark: "data:wordmark", emblem: "data:emblem"}, environment)
        .then((value) => {settled = true; return value;});
    images[0].onload();
    await Promise.resolve();
    assert.equal(settled, false);
    images[1].onload();
    const loaded = await loading;
    assert.equal(loaded.wordmark, images[0]);
    assert.equal(loaded.emblem, images[1]);
    const rejected = adapter.LoadBranding({wordmark: "broken"}, environment);
    images[2].onerror();
    await assert.rejects(rejected, /branding image/);
});

test("constant extreme domains label padded ticks without Infinity or false zero", () => {
    for (const value of [Number.MAX_VALUE, -Number.MAX_VALUE, 1e-308]) {
        const spec = Spec(1);
        spec.candles[0] = {...spec.candles[0], open: value, high: value, low: value, close: value};
        spec.series = [];
        spec.markers = [];
        const chart = NewChart(spec);
        const axis = chart.getModel().getComponent("yAxis", 0).axis;
        const formatter = chart.getOption().yAxis[0].axisLabel.formatter;
        const labels = axis.scale.getTicks().map((tick) => formatter(tick.value));
        assert.ok(labels.every((label) => !/Infinity|NaN/.test(label)));
        assert.ok(labels.some((label) => /e[-+]\d+/.test(label)));
        chart.dispose();
    }
});

test("unknown schemas fail closed before chart configuration", () => {
    assert.throws(() => adapter.BuildOptions({...Spec(), schema_version: 99}, theme, branding, 1280, 760), /schema/);
});

test("a hidden extreme overlay fails clearly instead of blanking ordinary prices", () => {
    const spec = Spec();
    spec.series[0].values = [1e308, 1e308, 1e308];
    assert.throws(() => adapter.BuildOptions(spec, theme, branding, 1280, 760), /rescale prices\/overlays/);
});

test("date labels preserve extended years and millisecond input precision", () => {
    const spec = Spec();
    spec.candles[1].datetime = "2026-01-01T00:00:00.001Z";
    spec.candles[2].datetime = "2026-01-01T00:00:00.002Z";
    const options = adapter.BuildOptions(spec, theme, branding, 1280, 760);
    const formatter = options.xAxis[1].axisLabel.formatter;
    assert.equal(formatter(Date.parse(spec.candles[1].datetime)), "2026-01-01\n00:00:00.001 UTC");
    assert.equal(formatter(Date.parse("+010000-01-01T00:00:00.000Z")), "+010000-01-01\n00:00:00.000 UTC");
});

test("accessible buttons wire real actions and group names stay plain text", () => {
    function Element(action) {
        return {dataset: {action}, attributes: {}, listeners: new Map(), children: [], textContent: "",
            addEventListener(type, handler) {this.listeners.set(type, handler);},
            removeEventListener(type) {this.listeners.delete(type);},
            setAttribute(key, value) {this.attributes[key] = value;},
            appendChild(child) {this.children.push(child);},
            click() {this.listeners.get("click")?.();}};
    }
    const spec = Spec(30);
    spec.series[0].group = '<img src="https://untrusted.example/">';
    const chart = NewChart(spec);
    const environment = Environment();
    const controller = adapter.CreateController(chart, spec, theme, branding, {}, environment);
    const buttons = ["pan", "box", "reset", "full", "export"].map(Element);
    const groups = Element();
    const controls = {querySelectorAll: () => buttons,
        querySelector: (selector) => selector === "[data-groups]" ? groups : buttons[1]};
    const created = [];
    environment.document = {createElement: (name) => {const element = Element();
        element.tagName = name; created.push(element); return element;}};
    const status = Element();
    adapter.AttachControls(controller, controls, status, environment);
    buttons[1].click();
    assert.equal(controller.boxZoom, true);
    assert.equal(buttons[1].attributes["aria-pressed"], "true");
    chart.dispatchAction({type: "takeGlobalCursor", key: "dataZoomSelect", dataZoomSelectActive: false});
    assert.equal(buttons[1].attributes["aria-pressed"], "false");
    assert.equal(groups.children[0].textContent, spec.series[0].group);
    assert.equal(groups.children[0].children.length, 0);
    groups.children[0].click();
    assert.equal(controller.Selected().__pg_overlay_sma, true);
    buttons[2].click();
    assert.equal(controller.Selected().__pg_overlay_sma, false);
    buttons[4].click();
    assert.equal(created.at(-1).download, "pricegenerator-chart.png");
    assert.match(created.at(-1).href, /^data:image\/png/);
    assert.equal(status.textContent, "PNG exported.");
    controller.Dispose();
    assert.ok(buttons.every((button) => button.listeners.size === 0));
});
