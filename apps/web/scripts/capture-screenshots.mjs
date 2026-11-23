import { chromium } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, '..');
const output = path.resolve(here, '../../../assets/screenshots');
const base = process.env.SCREENSHOT_BASE_URL || 'http://127.0.0.1:3000';
const pages = [
  { name: '01-landing-page', route: '/', expected: 'AI that shows its work' },
  { name: '02-executive-dashboard', route: '/demo', expected: 'Executive overview' },
  { name: '03-copilot-evidence', route: '/demo/copilot', expected: 'AI Operations Copilot' },
  { name: '04-sql-governance-drawer', route: '/demo/governance', expected: 'Governance, users & audit' },
  { name: '05-data-quality-center', route: '/demo/data-quality', expected: 'Data Quality Center' },
  { name: '06-alerts-command-center', route: '/demo/alerts', expected: 'Alerts & Watchlists' },
  { name: '07-watchlist-detail', route: '/demo/inventory', expected: 'Inventory Risk Center' },
  { name: '08-forecast-studio', route: '/demo/forecast', expected: 'Forecast Studio' },
  { name: '09-anomaly-explorer', route: '/demo/anomalies', expected: 'Anomaly Explorer' },
  { name: '10-decision-workbench', route: '/demo/workbench', expected: 'Decision Workbench' },
  {
    name: '11-scenario-comparison',
    route: '/demo/workbench',
    expected: 'Decision Workbench',
    setup: async (page) => {
      await page.locator('input[type="range"]').fill('80');
      await page.getByText('Scenario · PKR 364K', { exact: false }).waitFor();
    },
  },
  { name: '12-investigation-detail', route: '/demo/investigations', expected: 'Investigate Consumer Electronics' },
  {
    name: '13-approval-workflow',
    route: '/demo/investigations',
    expected: 'Investigate Consumer Electronics',
    setup: async (page) => {
      await page.getByRole('button', { name: 'Request approval' }).click();
      await page.getByText('Pending approval', { exact: true }).waitFor();
    },
  },
  { name: '14-ingestion-wizard', route: '/demo/ingestion', expected: 'Data Ingestion Center' },
  {
    name: '15-import-mapping',
    route: '/demo/ingestion',
    expected: 'Data Ingestion Center',
    setup: async (page) => {
      await page.getByRole('button', { name: 'Preview validation failure' }).click();
      await page.getByText('Validation failure', { exact: true }).waitFor();
    },
  },
  {
    name: '16-lineage-explorer',
    route: '/demo/ingestion',
    expected: 'Data Ingestion Center',
    setup: async (page) => {
      await page.getByRole('button', { name: 'Resolve mappings' }).click();
      await page.getByText('Validation passed.', { exact: false }).waitFor();
    },
  },
  { name: '17-metric-catalog', route: '/demo/metrics', expected: 'Metric Catalog' },
  { name: '18-reporting-center', route: '/demo/reports', expected: 'Reporting Center' },
  {
    name: '19-report-preview',
    route: '/demo/reports',
    expected: 'Reporting Center',
    setup: async (page) => {
      await page.getByRole('button', { name: 'Generate report' }).click();
      await page.getByText('Executive Operations Brief generated', { exact: false }).waitFor();
    },
  },
  { name: '20-security-center', route: '/demo/security', expected: 'Security Center' },
  { name: '21-operations-console', route: '/demo/operations', expected: 'Operations Console' },
  {
    name: '22-command-palette',
    route: '/demo',
    expected: 'Executive overview',
    setup: async (page) => {
      await page.getByRole('button', { name: /Command palette/ }).click();
      await page.getByPlaceholder('Search products, suppliers, alerts, reports, or actions…').waitFor();
    },
  },
  { name: '23-mobile-dashboard', route: '/demo/mobile', expected: "Today's operating priorities", mobile: true },
  {
    name: '25-generated-report-preview',
    route: '/demo/reports',
    expected: 'Reporting Center',
    setup: async (page) => {
      await page.getByRole('button', { name: 'Generate report' }).click();
      await page.getByRole('button', { name: 'Create schedule' }).click();
      await page.getByText('Schedule saved (simulated)', { exact: false }).waitFor();
    },
  },
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
  const launchOptions = { args: ['--no-sandbox'] };
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) {
    launchOptions.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  }
  const browser = await chromium.launch(launchOptions);
  const captures = [];
  for (const spec of pages) {
    const page = await browser.newPage({ viewport: { width: spec.mobile ? 390 : 1440, height: spec.mobile ? 844 : 900 }, deviceScaleFactor: 1 });
    const screenshotPath = path.join(output, `${spec.name}.png`);
    try {
      const response = await page.goto(`${base}${spec.route}`, { waitUntil: 'domcontentloaded', timeout: 15000 });
      if (!response || !response.ok()) throw new Error(`Route returned ${response?.status() ?? 'no response'}`);
      await page.getByText(spec.expected, { exact: false }).first().waitFor({ state: 'visible', timeout: 15000 });
      if (spec.setup) await spec.setup(page);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      captures.push({ name: spec.name, route: spec.route, status: response.status(), screenshot: screenshotPath });
    } catch (error) {
      const diagnosticsDir = path.join(output, 'capture-failures');
      await mkdir(diagnosticsDir, { recursive: true });
      await page.screenshot({ path: path.join(diagnosticsDir, `${spec.name}.png`), fullPage: true }).catch(() => undefined);
      await writeFile(path.join(diagnosticsDir, `${spec.name}.json`), JSON.stringify({ name: spec.name, route: spec.route, error: String(error) }, null, 2));
      throw new Error(`Capture failed for ${spec.name} (${spec.route}): ${String(error)}`);
    } finally {
      await page.close();
    }
  }
  await browser.close();
  const hashes = new Map();
  for (const capture of captures) {
    const hash = createHash('sha256').update(await readFile(capture.screenshot)).digest('hex');
    if (!hashes.has(hash)) hashes.set(hash, []);
    hashes.get(hash).push(capture.name);
  }
  const duplicateGroups = [...hashes.values()].filter((group) => group.length > 1);
  if (duplicateGroups.length) throw new Error(`Different claimed views rendered identical images: ${JSON.stringify(duplicateGroups)}`);
  await writeFile(path.join(output, 'capture-manifest.json'), JSON.stringify({ base, captures, duplicateGroups }, null, 2));
  console.log(`Captured ${captures.length} live Next.js application surfaces in ${output}`);
} finally {
  if (server?.pid) {
    if (process.platform !== 'win32') process.kill(-server.pid, 'SIGTERM');
    else server.kill('SIGTERM');
  }
}
