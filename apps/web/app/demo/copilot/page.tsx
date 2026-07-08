'use client';

import Link from 'next/link';
import { useState } from 'react';
import { AppShell } from '../../../components/app-shell';
import { ApiWorkflowPanel } from '../../../components/api-workflow-panel';

const modes = ['Executive Brief', 'Analyst View', 'Data Explorer', 'Investigation Mode', 'Forecast Explanation', 'Data Quality Explanation'];
const templates = ['Why is this SKU at risk?', 'Explain this chart', 'Compare Islamabad and Lahore', 'What should I prioritize?', 'Create report from this evidence'];

export default function Copilot() {
  const [mode, setMode] = useState(modes[0]);
  const [saved, setSaved] = useState(false);
  const [template, setTemplate] = useState<string | null>(null);
  const [reportCreated, setReportCreated] = useState(false);

  return <AppShell title="AI Operations Copilot">
    <div className="grid gap-3 xl:grid-cols-[245px_1fr_350px]">
      <aside className="card p-4">
        <p className="label">Answer mode</p>
        <div className="mt-3 space-y-1">{modes.map((item) => <button onClick={() => setMode(item)} key={item} className={`w-full rounded px-2 py-2 text-left text-xs ${mode === item ? 'bg-[#253529] text-[#bfe9c6]' : 'text-muted hover:bg-[#242925]'}`}>{item}</button>)}</div>
        <p className="label mt-6">Suggested question templates</p>
        {templates.map((item) => <button key={item} onClick={() => setTemplate(item)} className="mt-2 w-full rounded-md border border-line p-3 text-left text-xs text-[#cecdc4] hover:border-[#4d6253]">{item}</button>)}
        {template && <p className="mt-3 rounded border border-[#435f48] bg-[#1d2920] p-2 text-[10px] text-[#c5e9c9]">Template loaded: {template}</p>}
      </aside>
      <section className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="label">Governed AI analysis · {mode}</p><p className="mt-1 text-xs text-muted">Tenant-bound, certified-metric response</p></div><span className="chip text-signal">Supported question</span></div>
        <div className="mt-4 rounded-md border border-[#38403a] bg-[#1f2421] p-4 text-sm"><span className="label text-signal">You</span><p className="mt-2">Which products are likely to stock out within 14 days?</p></div>
        <div className="mt-4 flex flex-wrap gap-2">{['Intent classified', 'Metrics selected', 'Query plan created', 'AST validated', 'Evidence retrieved', 'Grounded answer'].map((item) => <span key={item} className="chip border-[#3a443c] bg-[#202922] text-[#b7d9be]">✓ {item}</span>)}</div>
        <div className="mt-4 rounded-md border border-[#38403a] bg-[#1f2421] p-4 text-sm"><div className="flex items-center justify-between"><span className="label text-signal">OpsLens AI · 78% confidence</span><span className="rounded bg-[#392d1b] px-2 py-1 text-[10px] text-[#ebc772]">Data-quality warning</span></div><p className="mt-3"><b>14 branch-SKU combinations are below their reorder policy.</b> The most urgent exposure is concentrated in Islamabad and Lahore. A 14-hour inventory freshness delay is retained as a visible limitation.</p><p className="mt-3 text-xs leading-5 text-muted">Recommended next step: open a simulated inventory-transfer scenario, inspect the effect on stockout risk, then request human approval. No ERP inventory is changed by this workflow.</p></div>
        <table className="table mt-4 w-full"><thead><tr><th>SKU</th><th>Product</th><th>Branch</th><th>Cover</th><th>Risk</th></tr></thead><tbody>{[['NSR-1037', 'Consumer Electronics Plus 38', 'Islamabad', '2.3 days', 'Critical'], ['NSR-1053', 'Home Appliances Essential 54', 'Lahore', '3.1 days', 'Critical'], ['NSR-1074', 'Mobile Accessories Pro 75', 'Islamabad', '4.4 days', 'High']].map((row) => <tr key={row[0]}>{row.map((value, index) => <td key={index}>{index === 4 ? <span className="rounded bg-[#412326] px-2 py-1 text-[10px] text-[#ffaaa5]">{value}</span> : value}</td>)}</tr>)}</tbody></table>
        <div className="mt-5 flex flex-wrap gap-2"><button onClick={() => setSaved(!saved)} className="rounded-md border border-line px-3 py-2 text-xs">{saved ? 'Saved answer' : 'Save answer'}</button><button onClick={() => setReportCreated(true)} className="rounded-md border border-line px-3 py-2 text-xs">{reportCreated ? 'Report draft created' : 'Create report'}</button><Link href="/demo/workbench" className="rounded-md bg-[#e6e2d6] px-3 py-2 text-xs font-bold text-[#181a18]">Start scenario</Link></div>
        {reportCreated && <p className="mt-3 rounded border border-[#435f48] bg-[#1d2920] p-3 text-xs text-[#c5e9c9]">Executive report draft created with the answer, SQL validation, evidence, and data-quality notice attached.</p>}
      </section>
      <aside className="card p-4"><p className="label">Query plan</p><div className="mt-3 space-y-2 text-xs"><p><span className="text-muted">Intent</span><br/><b>stockout_risk</b></p><p><span className="text-muted">Metrics</span><br/><b>Stock cover · Stockout risk</b></p><p><span className="text-muted">Tenant filter</span><br/><b>organization_id = :organization_id</b></p><p><span className="text-muted">Budget</span><br/><b>24 rows · 5,000 ms</b></p></div><p className="label mt-5">Validated SQL</p><pre className="mt-3 overflow-auto rounded-md border border-line bg-canvas p-3 text-[10px] leading-5 text-[#d3ead8]">{`SELECT p.sku, p.name, b.name AS branch,
i.available_units, p.reorder_point
FROM inventory_records i
JOIN products p ON p.id = i.product_id
JOIN branches b ON b.id = i.branch_id
WHERE i.organization_id = :organization_id
AND i.available_units <= p.reorder_point
ORDER BY i.available_units ASC LIMIT 24`}</pre><p className="label mt-5">AST validation result</p>{['One SELECT / CTE statement', 'Approved tables and joins', 'Tenant bind parameter present', 'No DDL, DML, filesystem or network functions', 'Row and complexity budgets passed'].map((item) => <p key={item} className="border-b border-line py-2 text-xs text-[#b9c2b9]"><span className="mr-2 text-signal">✓</span>{item}</p>)}</aside>
    </div>
  <ApiWorkflowPanel title="Copilot evidence API contract" endpoint="/api/v1/ai/conversations" summary="Uses the live AI conversation boundary. The supported-question workflow persists query plans, SQL validation, evidence, and audit events." mutations={[{label: "Create conversation", path: "/api/v1/ai/conversations", body: {"title": "Phase 3 stockout analysis", "mode": "Investigation Mode"}}]}/></AppShell>;
}