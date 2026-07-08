import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, '..');
const output = path.resolve(here, '../../../screenshots');
const base = process.env.SCREENSHOT_BASE_URL || 'http://127.0.0.1:3000';
const pages = [
  ['landing', '/'],
  ['executive-overview', '/demo'],
  ['ai-copilot-v2', '/demo/copilot'],
  ['data-quality-center', '/demo/data-quality'],
  ['alerts-watchlists', '/demo/alerts'],
  ['forecast-studio', '/demo/forecast'],
  ['anomaly-explorer', '/demo/anomalies'],
  ['decision-workbench', '/demo/workbench'],
  ['investigation-detail', '/demo/investigations'],
  ['data-ingestion', '/demo/ingestion'],
  ['metric-catalog', '/demo/metrics'],
  ['reporting-center', '/demo/reports'],
  ['security-center', '/demo/security'],
  ['global-search', '/demo/search'],
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function isReady() {
  try { return (await fetch(`${base}/`)).ok; } catch { return false; }
}

let server;
if (!(await isReady())) {
  server = spawn('npm', ['run', 'dev', '--', '-p', '3000'], {
    cwd: webRoot,
    stdio: 'ignore',
    detached: process.platform !== 'win32',
  });
  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (await isReady()) break;
    await sleep(500);
  }
  if (!(await isReady())) throw new Error(`Next.js did not become available at ${base}`);
}

async function serverRenderedDocument(route) {
  const response = await fetch(`${base}${route}`);
  if (!response.ok) throw new Error(`Could not retrieve ${route}: ${response.status}`);
  let html = await response.text();
  const cssHrefs = [...html.matchAll(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"[^>]*>/g)].map((match) => match[1]);
  const css = await Promise.all(cssHrefs.map(async (href) => `<style>${await fetch(new URL(href, base)).then((item) => item.text())}</style>`));
  // Managed Chromium in this environment blocks all HTTP navigation. Rendering this
  // server-rendered Next.js document with its actual generated CSS keeps the captures
  // reproducible without replacing the product UI with an unrelated static mockup.
  html = html.replace(/<link[^>]+rel="stylesheet"[^>]*>/g, css.join('\n'));
  html = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '');
  html = html.replace(/<script\b[^>]*\/?>/g, '');
  return html;
}

try {
  await mkdir(output, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || '/usr/bin/chromium',
    args: ['--no-sandbox'],
  });
  for (const [name, route] of pages) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
    await page.setContent(await serverRenderedDocument(route), { waitUntil: 'domcontentloaded' });
    await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: true });
    await page.close();
  }
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  await mobile.setContent(await serverRenderedDocument('/demo/mobile'), { waitUntil: 'domcontentloaded' });
  await mobile.screenshot({ path: path.join(output, 'mobile-executive.png'), fullPage: true });
  await mobile.close();
  await browser.close();
  console.log(`Captured ${pages.length + 1} server-rendered Next.js application surfaces in ${output}`);
} finally {
  if (server?.pid) {
    if (process.platform !== 'win32') process.kill(-server.pid, 'SIGTERM');
    else server.kill('SIGTERM');
  }
}
