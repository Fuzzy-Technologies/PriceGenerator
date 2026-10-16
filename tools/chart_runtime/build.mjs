// Rebuild explicitly; neither Python installation nor chart generation runs Node.
import { build } from 'esbuild';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { gzipSync } from 'node:zlib';

const here = dirname(fileURLToPath(import.meta.url));
const output = resolve(here, '../../pricegenerator/rendering/assets/echarts');
await build({
  entryPoints: [resolve(here, 'entry.mjs')],
  outfile: resolve(output, 'echarts-financial.min.js'),
  bundle: true, minify: true, format: 'iife', globalName: 'PriceGeneratorCharts',
  target: ['es2020'], legalComments: 'eof',
  banner: {js: '/*! Apache ECharts 6.1.0 financial build; Apache-2.0. See embedded third-party notices. */'},
});
const bytes = await readFile(resolve(output, 'echarts-financial.min.js'));
const lock = JSON.parse(await readFile(resolve(here, 'package-lock.json'), 'utf8'));
const metadata = {
  echarts_version: lock.packages['node_modules/echarts'].version,
  echarts_source: lock.packages['node_modules/echarts'].resolved,
  echarts_source_integrity: lock.packages['node_modules/echarts'].integrity,
  zrender_version: lock.packages['node_modules/zrender'].version,
  tslib_version: lock.packages['node_modules/tslib'].version,
  builder_version: lock.packages['node_modules/esbuild'].version,
  sha256: createHash('sha256').update(bytes).digest('hex'),
  raw_bytes: bytes.length,
  gzip_bytes: gzipSync(bytes, {level: 9}).length,
};
await writeFile(resolve(output, 'build.json'), `${JSON.stringify(metadata, null, 2)}\n`);
console.log(JSON.stringify(metadata, null, 2));
