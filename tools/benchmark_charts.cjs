/* Diagnostic real-Canvas measurements. This is not a browser or display-FPS test. */
"use strict";
const assert = require("node:assert/strict");
const {createHash} = require("node:crypto");
const {readFileSync} = require("node:fs");
const {createRequire} = require("node:module");
const os = require("node:os");
const path = require("node:path");
const {performance} = require("node:perf_hooks");

function Element(name) {
    const listeners = new Map();
    return {name, dataset: {}, children: [], attributes: {},
        addEventListener(type, callback) {listeners.set(type, callback);},
        removeEventListener(type) {listeners.delete(type);},
        setAttribute(key, value) {this.attributes[key] = value;},
        appendChild(child) {this.children.push(child);},
        click() {const listener = listeners.get("click"); if (listener) listener();}};
}

function Controls(environment) {
    const originalCreate = environment.document.createElement;
    environment.document.createElement = (name) => name === "canvas" ? originalCreate(name) : Element(name);
    const groups = Element("span");
    const buttons = ["pan", "box", "reset", "full", "export"].map((action) => {
        const element = Element("button"); element.dataset.action = action; return element;
    });
    return {querySelectorAll() {return buttons;}, querySelector(selector) {
        return selector === "[data-groups]" ? groups : buttons.find((button) => button.dataset.action === "box");
    }};
}

function ReadBlock(html, id) {
    const match = html.match(new RegExp('<script id="' + id + '" type="application/json">([\\s\\S]*?)</script>'));
    assert.ok(match, "The exported HTML must contain " + id);
    return JSON.parse(match[1]);
}

function VisibleRows(chart) {
    return {price: chart.getModel().getSeriesByIndex(0).getData().count(),
        volume: chart.getModel().getSeriesByIndex(1).getData().count()};
}

function Measure(chart, operation) {
    const started = performance.now();
    operation();
    chart.getZr().flush();
    return {milliseconds: performance.now() - started, visible_rows: VisibleRows(chart)};
}

async function Main(arguments_) {
    const [sourceRoot, canvasModule, htmlPath] = arguments_;
    assert.ok(sourceRoot && canvasModule && htmlPath, "Expected source root, Canvas module and HTML path");
    const resolveFrom = createRequire(path.join(sourceRoot, "tools/chart_runtime/package.json"));
    const resolvedCanvas = resolveFrom.resolve(canvasModule);
    const canvasPackage = resolveFrom(canvasModule + "/package.json");
    const {CreateHarness} = require(path.join(sourceRoot, "tools/chart_runtime/canvas_environment.cjs"));
    const adapter = require(path.join(sourceRoot, "pricegenerator/rendering/assets/interactive.js"));
    const harness = CreateHarness(resolvedCanvas);
    const html = readFileSync(htmlPath, "utf8");
    const parseStarted = performance.now();
    const spec = ReadBlock(html, "chart-spec");
    const theme = ReadBlock(html, "chart-theme");
    const branding = ReadBlock(html, "chart-branding");
    const parseMilliseconds = performance.now() - parseStarted;
    const controls = Controls(harness.environment);
    const status = {textContent: ""};
    const canvas = harness.Canvas(spec.width, spec.height);
    const mountStarted = performance.now();
    const controller = await adapter.Mount(canvas, spec, theme, branding, controls,
        status, harness.runtime, harness.environment);
    controller.chart.getZr().flush();
    const mountMilliseconds = performance.now() - mountStarted;
    const chart = controller.chart;
    const count = spec.candles.length;
    const expectedInitial = count > 5000 ? 1000 : count;
    const initialRows = VisibleRows(chart);
    const result = {status: "ok", total_rows: count,
        environment: {node: process.version, platform: process.platform, architecture: process.arch,
            os_release: os.release(), cpu_model: os.cpus()[0]?.model ?? null,
            cpu_count: os.cpus().length, echarts: harness.engine.version,
            canvas: canvasPackage.version, pixel_ratio: 2, renderer: "native Canvas, ssr=true",
            timers: "ECharts animation timers suppressed by shared raster harness; animation and progressive rendering disabled"},
        html_json_parse_ms: parseMilliseconds, mount_ms: mountMilliseconds, initial_visible_rows: initialRows,
        scope: {mount: "Brand image decode/tint, real ECharts init and setOption, control binding shim and raster flush",
            actions: "Synchronous real ECharts dispatch/setOption plus Canvas raster flush; excludes OS input, DOM layout and display frames",
            update: "Replace complete candle data array after increasing final high by 0.01; array preparation excluded",
            png: "Actual controller ExportPNG at pixel ratio 2; decoding and hashing excluded"},
        actions: {}};

    try {
        assert.equal(chart.getOption().animation, false, "Timing requires animation to remain disabled");
        assert.ok(chart.getOption().series.every((series) => series.progressive === 0), "Timing requires synchronous complete drawing");
        assert.deepEqual(initialRows, {price: expectedInitial, volume: expectedInitial}, "Initial visible count must match the renderer policy");
        assert.equal(chart.getOption().series[0].data.length, count, "The viewport must retain the complete input dataset");
        const exportStarted = performance.now();
        const png = controller.ExportPNG();
        result.png_export_ms = performance.now() - exportStarted;
        const pngBytes = Buffer.from(png.split(",")[1], "base64");
        assert.ok(pngBytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), "Export must contain a real PNG");
        const decoded = await harness.DecodePNG(png);
        assert.equal(decoded.width, spec.width * 2);
        assert.equal(decoded.height, spec.height * 2);
        result.png = {bytes: pngBytes.length, width: decoded.width, height: decoded.height,
            sha256: createHash("sha256").update(pngBytes).digest("hex")};

        const windowSize = Math.min(250, Math.floor(count / 2));
        const zoomStart = Date.parse(spec.candles[count - windowSize].datetime) - 30000;
        const zoomEnd = Date.parse(spec.candles[count - 1].datetime) + 30000;
        result.actions.zoom = Measure(chart, () => chart.dispatchAction({type: "dataZoom", startValue: zoomStart, endValue: zoomEnd}));
        assert.deepEqual(result.actions.zoom.visible_rows, {price: windowSize, volume: windowSize});
        result.actions.pan = Measure(chart, () => chart.dispatchAction({type: "dataZoom",
            startValue: zoomStart - windowSize * 60000, endValue: zoomEnd - windowSize * 60000}));
        assert.deepEqual(result.actions.pan.visible_rows, {price: windowSize, volume: windowSize});
        result.actions.reset = Measure(chart, () => controller.Reset());
        assert.deepEqual(result.actions.reset.visible_rows, initialRows);

        const data = chart.getOption().series[0].data;
        data[data.length - 1][4] += 0.01;
        result.actions.update = Measure(chart, () => chart.setOption({series: [{id: "__pg_price", data}]}));
        assert.deepEqual(result.actions.update.visible_rows, initialRows);
        result.actions.full_range = Measure(chart, () => controller.FullRange());
        assert.deepEqual(result.actions.full_range.visible_rows, {price: count, volume: count});
        result.process_peak_rss_bytes = process.resourceUsage().maxRSS * 1024;

    } finally {
        controller.Dispose();
    }

    assert.equal(harness.events.size, 0, "The benchmark must release its lifecycle listeners");
    return result;
}

if (require.main === module) {
    Main(process.argv.slice(2)).then((result) => console.log(JSON.stringify(result)))
        .catch((error) => {console.log(JSON.stringify({status: "error",
            error: {type: error.name, message: error.message}})); process.exitCode = 1;});
}

module.exports = {ReadBlock, Main};
