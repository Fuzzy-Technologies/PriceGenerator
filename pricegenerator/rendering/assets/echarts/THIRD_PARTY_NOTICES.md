# Bundled financial chart runtime

The interactive renderer embeds a reduced Apache ECharts **6.1.0** Canvas build.
It does not load scripts, fonts, telemetry, or images from a CDN. The vendored
runtime is derived from official npm release sources, pinned by the lockfile
in `tools/chart_runtime/`. `build.json` records upstream package integrity,
builder versions, the resulting SHA-256, and compressed/uncompressed byte sizes.

| Shipped component | Version | License | Retained license |
| --- | --- | --- | --- |
| Apache ECharts | 6.1.0 | Apache-2.0 | `LICENSE-APACHE-2.0.txt`, `NOTICE.txt` |
| ZRender | 6.1.0 | BSD-3-Clause | `LICENSE-ZRENDER-BSD-3.txt` |
| tslib | 2.3.0 | 0BSD | `LICENSE-TSLIB-0BSD.txt` |

ZRender and tslib are permissive transitive dependencies of ECharts. ECharts
itself meets the MIT/Apache backend requirement; the dependency inventory is
explicit rather than claiming that every transitive source is Apache-licensed.
Complete notices above are also included in each generated HTML document.

The exact modules are listed in `tools/chart_runtime/entry.mjs`. The custom
financial build removes unused chart families; it does not modify upstream
source behavior. Source origin: https://github.com/apache/echarts/tree/6.1.0
and https://www.npmjs.com/package/echarts/v/6.1.0.

Rebuild from the repository root:

```sh
cd tools/chart_runtime
npm ci
npm run build
```

Node and esbuild are maintainer build tools, not Python install/runtime
dependencies. Built files are checked into the package so an installed wheel
works offline with Python's standard library. Include the full `assets/`
directory in wheels and source distributions.
