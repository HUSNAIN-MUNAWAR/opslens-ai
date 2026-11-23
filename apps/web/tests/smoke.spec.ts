import { test, expect } from '@playwright/test';

test('demo login landing and executive command center render', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('AI that shows its work before you act.')).toBeVisible();
  await page.goto('/demo');
  await expect(page.getByRole('heading', { name: 'Executive overview' })).toBeVisible();
  await expect(page.getByText('Priorities for today')).toBeVisible();
  await page.getByText('Open governed workflow').first().click();
  await expect(page.getByText('Decision Workbench')).toBeVisible();
});

test('copilot displays evidence then creates an attached report draft', async ({ page }) => {
  await page.goto('/demo/copilot');
  await expect(page.getByText('Validated SQL', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('AST validation result')).toBeVisible();
  await expect(page.getByText('Data-quality warning')).toBeVisible();
  await page.getByText('Create report').click();
  await expect(page.getByText('Executive report draft created')).toBeVisible();
});

test('data-quality issue can be acknowledged and routed to investigation workflow', async ({ page }) => {
  await page.goto('/demo/data-quality');
  await page.getByText('Acknowledge').first().click();
  await expect(page.getByText('Acknowledged', { exact: true }).last()).toBeVisible();
  await page.getByText('Create investigation from selected issue').click();
  await expect(page.getByText('Draft investigation created')).toBeVisible();
  await page.getByText('Open investigation workflow').click();
  await expect(page.getByText('Investigate Consumer Electronics margin erosion')).toBeVisible();
});

test('decision workbench requests a simulated approval', async ({ page }) => {
  await page.goto('/demo/workbench');
  await page.getByRole('button', { name: 'Request approval for simulation', exact: true }).click();
  await expect(page.getByText('Approval request created')).toBeVisible();
  await expect(page.getByText(/no ERP writeback/i)).toBeVisible();
});

test('CSV ingestion surfaces validation failure and a complete import state', async ({ page }) => {
  await page.goto('/demo/ingestion');
  await page.getByRole('button', { name: 'Preview validation failure', exact: true }).click();
  await expect(page.getByText('Validation failure')).toBeVisible();
  await page.getByText('Resolve mappings').click();
  await expect(page.getByText('Validation passed')).toBeVisible();
  await page.getByText('Complete import').click();
  await expect(page.getByText('Import complete')).toBeVisible();
});

test('workspace switcher and global command palette expose tenant context', async ({ page }) => {
  await page.goto('/demo');
  await page.getByText('Northstar Retail Group').first().click();
  await page.getByText('Crescent Commerce Co.').first().click();
  await expect(page.getByText('Workspace context changed to Crescent Commerce Co.')).toBeVisible();
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K');
  await expect(page.getByPlaceholder('Search products, suppliers, alerts, reports, or actions…')).toBeVisible();
  await page.getByText('Data Quality Center').last().click();
  await expect(page.getByText('Data Quality Center')).toBeVisible();
});
