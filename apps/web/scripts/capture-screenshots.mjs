import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, '..');
const output = path.resolve(here, '../../../assets/screenshots');
const base = process.env.SCREENSHOT_BASE_URL || 'http://127.0.0.1:3000';
const pages = [
  { name: '01-landing-page', route: '/' },
  { name: '02-executive-dashboard', route: '/demo' },
  { name: '03-copilot-evidence', route: '/demo/copilot' },
  { name: '04-sql-governance-drawer', route: '/demo/governance' },
  { name: '05-data-quality-center', route: '/demo/data-quality' },
  { name: '06-alerts-command-center', route: '/demo/alerts' },
  { name: '07-watchlist-detail', route: '/demo/inventory' },
  { name: '08-forecast-studio', route: '/demo/forecast' },
  { name: '09-anomaly-explorer', route: '/demo/anomalies' },
  { name: '10-decision-workbench', route: '/demo/workbench' },
  { name: '11-scenario-comparison', route: '/demo/workbench', setup: async (page) => page.locator('input[type="range"]').fill('80') },
  { name: '12-investigation-detail', route: '/demo/investigations' },
  { name: '13-approval-workflow', route: '/demo/investigations', setup: async (page) => page.getByRole('button', { name: 'Request approval' }).click() },
  { name: '14-ingestion-wizard', route: '/demo/ingestion' },
  { name: '15-import-mapping', route: '/demo/ingestion', setup: async (page) => page.getByRole('button', { name: 'Preview validation failure' }).click() },
  { name: '16-lineage-explorer', route: '/demo/ingestion', setup: async (page) => page.getByRole('button', { name: 'Resolve mappings' }).click() },
  { name: '17-metric-catalog', route: '/demo/metrics' },
  { name: '18-reporting-center', route: '/demo/reports' },
  { name: '19-report-preview', route: '/demo/reports', setup: async (page) => page.getByRole('button', { name: 'Generate report' }).click() },
  { name: '20-security-center', route: '/demo/security' },
  { name: '21-operations-console', route: '/demo/operations' },
  { name: '22-command-palette', route: '/demo', setup: async (page) => page.getByRole('button', { name: /Command palette/ }).click() },
  { name: '23-mobile-dashboard', route: '/demo/mobile', mobile: true },
  { name: '25-generated-report-preview', route: '/demo/reports', setup: async (page) => { await page.getByRole('button', { name: 'Generate report' }).click(); await page.getByRole('button', { name: 'Create schedule' }).click(); } },
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

try {
  await mkdir(output, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || '/usr/bin/chromium',
    args: ['--no-sandbox'],
  });
  for (const spec of pages) {
    const page = await browser.newPage({ viewport: { width: spec.mobile ? 390 : 1440, height: spec.mobile ? 844 : 900 }, deviceScaleFactor: 1 });
    await page.goto(`${base}${spec.route}`, { waitUntil: 'networkidle' });
    if (spec.setup) await spec.setup(page);
    await page.screenshot({ path: path.join(output, `${spec.name}.png`), fullPage: true });
    await page.close();
  }
  await browser.close();
  console.log(`Captured ${pages.length} live Next.js application surfaces in ${output}`);
} finally {
  if (server?.pid) {
    if (process.platform !== 'win32') process.kill(-server.pid, 'SIGTERM');
    else server.kill('SIGTERM');
  }
}
