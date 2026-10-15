/* Real raster surface for deterministic engine/export tests; no browser emulation. */
"use strict";
const {readFileSync} = require("node:fs");
const path = require("node:path");

function CreateHarness(canvasModule = path.join(__dirname, "node_modules/@napi-rs/canvas")) {
    const native = require(canvasModule);
    function Canvas(width = 1, height = 1) {
        const canvas = native.createCanvas(width, height);
        // Browser DOM canvases/images are preserved by reference. Mark native equivalents likewise.
        Object.defineProperty(canvas, Symbol.toStringTag, {value: "Canvas"});
        return canvas;
    }
    const events = new Map();
    const environment = {
        Image: class extends native.Image {
            constructor() {super(); Object.defineProperty(this, Symbol.toStringTag, {value: "Image"});}
        },
        document: {createElement(name) {
            if (name !== "canvas") throw new Error("The raster harness only creates Canvas elements");
            return Canvas();
        }},
        addEventListener(name, handler) {events.set(name, handler);},
        removeEventListener(name) {events.delete(name);},
    };
    const source = readFileSync(path.resolve(__dirname,
        "../../pricegenerator/rendering/assets/echarts/echarts-financial.min.js"), "utf8");
    const engine = Function("setTimeout", "clearTimeout", source + ";return PriceGeneratorCharts;")(() => 0, () => {});
    engine.setPlatformAPI({createCanvas: Canvas});
    const runtime = {init(canvas, theme, options) {
        return engine.init(canvas, theme, {...options, ssr: true, width: canvas.width, height: canvas.height});
    }};
    async function DecodePNG(dataURI) {
        const image = await native.loadImage(dataURI);
        const canvas = Canvas(image.width, image.height);
        const context = canvas.getContext("2d");
        context.drawImage(image, 0, 0);
        return {width: image.width, height: image.height,
            pixels: context.getImageData(0, 0, image.width, image.height).data};
    }
    return {environment, Canvas, runtime, engine, DecodePNG, events};
}

module.exports = {CreateHarness};
