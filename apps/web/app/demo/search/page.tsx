import Link from 'next/link';
import { AppShell } from '../../../components/app-shell';
import { ApiWorkflowPanel } from '../../../components/api-workflow-panel';

const results: Array<[string, string, string, string, string]> = [
  ['Product', 'NSR-1037 · Consumer Electronics Plus 38', 'Stock cover 2.3 days', 'Critical', '/demo/inventory'],
  ['Alert', 'Forecasted stockout in Islamabad', 'Inventory · open', 'Critical', '/demo/alerts'],
  ['Metric', 'Stockout Risk', 'Certified metric · warning source', 'Warning', '/demo/metrics'],
  ['Investigation', 'Protect high-velocity demand', 'Investigating · owner Sara Malik', 'Open', '/demo/investigations'],
  ['Scenario', 'Transfer 40 units to Islamabad', 'Pending approval · simulated', 'Simulated', '/demo/workbench'],
  ['Report', 'Inventory Risk Report', 'Generated yesterday', 'Generated', '/demo/reports'],
];

export default function Search() {
  return <AppShell title="Global Search"><section><h1 className="text-3xl font-bold tracking-tight">Global entity search</h1><p className="mt-1 text-sm text-muted">Tenant-scoped lookup across products, suppliers, alerts, reports, investigations, metrics, and scenarios.</p></section><div className="mt-5 max-w-3xl rounded-xl border border-[#4a504a] bg-[#191c1a] p-5"><input autoFocus defaultValue="stock" aria-label="Search workspace entities" className="w-full rounded-lg border border-line bg-[#101212] px-4 py-3 text-sm outline-none"/><p className="mt-4 text-[10px] uppercase tracking-[.14em] text-muted">Results in Northstar Retail Group</p><div className="mt-2 space-y-1">{results.map((result) => <Link href={result[4]} className="flex w-full items-center justify-between rounded-lg p-3 text-left hover:bg-[#252a27]" key={result[1]}><span><span className="text-[10px] text-signal">{result[0].toUpperCase()}</span><b className="ml-2 text-sm">{result[1]}</b><p className="mt-1 text-xs text-muted">{result[2]}</p></span><span className="chip text-[9px]">{result[3]}</span></Link>)}</div></div><p className="mt-4 text-xs text-muted">Keyboard shortcut: Ctrl / ⌘ K. Search results respect workspace membership and role visibility at the API boundary.</p><ApiWorkflowPanel title="Global Search live entity results" endpoint="/api/v1/search?q=stock" summary="Searches products, suppliers, alerts, reports, scenarios, metrics, and data sources through the tenant-scoped API."/></AppShell>;
}