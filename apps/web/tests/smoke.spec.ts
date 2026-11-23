import { test, expect } from '@playwright/test';

test('demo login landing and executive command center render', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('AI that shows its work before you act.')).toBeVisible();
  await page.goto('/demo');
  await expect(page.getByRole('heading', { name: 'Executive overview', exact: true }).first()).toBeVisible();
  await expect(page.getByText('Priorities for today', { exact: true }).first()).toBeVisible();
  await page.getByText('Open governed workflow').first().click();
  await expect(page.getByText('Decision Workbench')).toBeVisible();
});

test('copilot displays evidence then creates an attached report draft', async ({ page }) => {
  await page.goto('/demo/copilot');
  await expect(page.getByText('Validated SQL', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('AST validation result', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Data-quality warning', { exact: true }).first()).toBeVisible();
  await page.getByText('Create report').click();
  await expect(page.getByText('Executive report draft created')).toBeVisible();
});

test('data-quality issue can be acknowledged and routed to investigation workflow', async ({ page }) => {
  await page.goto('/demo/data-quality');
  const qualityTable = page.locator('table').first();
  const firstIssue = qualityTable.getByRole('button').first();
  await firstIssue.click();
  await expect(firstIssue).toHaveText('Acknowledged');
  await page.getByRole('button', { name: 'Create investigation from selected issue', exact: true }).first().click();
  await expect(page.getByText('Draft investigation created', { exact: false }).first()).toBeVisible();
  await page.getByText('Open investigation workflow', { exact: true }).first().click();
  await expect(page.getByText('Investigate Consumer Electronics margin erosion', { exact: true }).first()).toBeVisible();
});

test('decision workbench requests a simulated approval', async ({ page }) => {
  await page.goto('/demo/workbench');
  await page.getByRole('button', { name: 'Request approval for simulation', exact: true }).click();
  await expect(page.getByText('Approval request created in', { exact: false }).first()).toBeVisible();
  await expect(page.getByText(/no ERP writeback/i).first()).toBeVisible();
});

test('CSV ingestion surfaces validation failure and a complete import state', async ({ page }) => {
  await page.goto('/demo/ingestion');
  await page.getByRole('button', { name: 'Preview validation failure', exact: true }).click();
  await expect(page.getByText('Validation failure', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Resolve mappings', exact: true }).first().click();
  await expect(page.getByText('Validation passed', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Complete import', exact: true }).first().click();
  await expect(page.getByText('Import complete', { exact: false }).first()).toBeVisible();
});

test('workspace switcher and global command palette expose tenant context', async ({ page }) => {
  await page.goto('/demo');
  await page.getByText('Northstar Retail Group').first().click();
  await page.getByText('Crescent Commerce Co.').first().click();
  await expect(page.getByText('Workspace context changed to Crescent Commerce Co.')).toBeVisible();
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K');
  await expect(page.getByPlaceholder('Search products, suppliers, alerts, reports, or actions…')).toBeVisible();
  await page.locator('a[href="/demo/data-quality"]').last().click({ force: true });
  await expect(page.getByRole('heading', { name: 'Data Quality Center', exact: true }).first()).toBeVisible();
});
