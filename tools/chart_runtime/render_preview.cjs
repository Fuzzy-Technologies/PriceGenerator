/* Optional raster QA: use an explicit @napi-rs/canvas installation, never a browser. */
"use strict";
const assert = require("node:assert/strict");
const {readFileSync, writeFileSync} = require("node:fs");
const path = require("node:path");
const [canvasModule, htmlPath, outputPath] = process.argv.slice(2);
if (!canvasModule || !htmlPath || !outputPath) {
    throw new Error("Usage: node render_preview.cjs <canvas-module> <chart.html> <preview.png>");
}
const {createCanvas, Image} = require(path.resolve(canvasModule));
const root = path.resolve(__dirname, "../..");
const adapter = require(path.join(root, "pricegenerator/rendering/assets/interactive.js"));
const runtime = Function("setTimeout", "clearTimeout", readFileSync(path.join(root,
    "pricegenerator/rendering/assets/echarts/echarts-financial.min.js"), "utf8") +
    ";return PriceGeneratorCharts;")(() => 0, () => {});
const html = readFileSync(htmlPath, "utf8");
function ReadBlock(id) {
    return JSON.parse(html.match(new RegExp('<script id="' + id + '" type="application/json">([\\s\\S]*?)</script>'))[1]);
}
function Canvas(width = 1, height = 1) {
    const canvas = createCanvas(width, height);
    Object.defineProperty(canvas, Symbol.toStringTag, {value: "Canvas"});
    return canvas;
}
const environment = {
    Image: class extends Image {
        constructor() {super(); Object.defineProperty(this, Symbol.toStringTag, {value: "Image"});}
    },
    document: {createElement: (name) => {assert.equal(name, "canvas"); return Canvas();}},
};
function ChangedPixels(first, second, width, rectangle) {
    let changed = 0;
    for (let y = rectangle.y; y < rectangle.y + rectangle.height; y += 1) {
        for (let x = rectangle.x; x < rectangle.x + rectangle.width; x += 1) {
            const position = (y * width + x) * 4;
            if (first[position] !== second[position] || first[position + 1] !== second[position + 1] ||
                first[position + 2] !== second[position + 2]) changed += 1;
        }
    }
    return changed;
}
(async () => {
    const spec = ReadBlock("chart-spec");
    const theme = ReadBlock("chart-theme");
    const images = await adapter.LoadBranding(ReadBlock("chart-branding"), environment);
    images.watermark = adapter.TintWatermark(images.wordmark, theme, environment);
    const measurement = Canvas().getContext("2d");
    runtime.setPlatformAPI({createCanvas: Canvas, measureText(text, font) {
        measurement.font = font;
        return measurement.measureText(text.replace(/\0/g, "\ufffd"));
    }});
    const canvas = Canvas(spec.width, spec.height);
    const chart = runtime.init(canvas, null, {renderer: "canvas", ssr: true,
        width: spec.width, height: spec.height});
    const options = adapter.BuildOptions(spec, theme, images, spec.width, spec.height);
    chart.setOption(options);
    chart.getZr().flush();
    const context = canvas.getContext("2d");
    const branded = context.getImageData(0, 0, spec.width, spec.height).data;
    writeFileSync(outputPath, Buffer.from(chart.getDataURL({type: "png", pixelRatio: 1,
        backgroundColor: theme.background, excludeComponents: ["toolbox"]}).split(",")[1], "base64"));
    chart.setOption({graphic: []}, {replaceMerge: ["graphic"]});
    chart.getZr().flush();
    const plain = context.getImageData(0, 0, spec.width, spec.height).data;
    const rectangles = [
        {name: "header emblem", x: 20, y: 15, width: 46, height: 46},
        ...options.graphic.filter((element) => element.id.startsWith("watermark-")).map((element) => ({
            name: element.id, x: Math.floor(element.style.x), y: Math.floor(element.style.y),
            width: Math.ceil(element.style.width), height: Math.ceil(element.style.height)})),
    ];
    const evidence = rectangles.map((rectangle) => ({region: rectangle.name,
        changed_pixels: ChangedPixels(branded, plain, spec.width, rectangle)}));
    for (const region of evidence) assert.ok(region.changed_pixels > 10,
        region.region + " must be visibly present in the actual Canvas output");
    assert.ok(readFileSync(outputPath).subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])));
    chart.dispose();
    console.log(JSON.stringify({runtime: runtime.version, output: outputPath, evidence}, null, 2));
})().catch((error) => {console.error(error); process.exitCode = 1;});
