'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Activity, AlertTriangle, BarChart3, Bell, BookOpen, Bot, Boxes, Command,
  Database, FileBarChart, Gauge, GitBranch, LineChart, Menu, Network,
  Search, Settings2, ShieldCheck, SlidersHorizontal, Sparkles, UploadCloud,
  Workflow, X,
} from 'lucide-react';

type Props = { title: string; children: ReactNode };

type Item = { label: string; href: string; icon: typeof Gauge; group: string };

const nav: Item[] = [
  { label: 'Executive overview', href: '/demo', icon: Gauge, group: 'Decision intelligence' },
  { label: 'AI Operations Copilot', href: '/demo/copilot', icon: Bot, group: 'Decision intelligence' },
  { label: 'Alerts & Watchlists', href: '/demo/alerts', icon: AlertTriangle, group: 'Decision intelligence' },
  { label: 'Forecast Studio', href: '/demo/forecast', icon: LineChart, group: 'Decision intelligence' },
  { label: 'Anomaly Explorer', href: '/demo/anomalies', icon: Activity, group: 'Decision intelligence' },
  { label: 'Decision Workbench', href: '/demo/workbench', icon: SlidersHorizontal, group: 'Decision intelligence' },
  { label: 'Inventory Risk Center', href: '/demo/inventory', icon: Boxes, group: 'Operations' },
  { label: 'Margin & Sales', href: '/demo/margin', icon: BarChart3, group: 'Operations' },
  { label: 'Investigations', href: '/demo/investigations', icon: Workflow, group: 'Operations' },
  { label: 'Data Quality Center', href: '/demo/data-quality', icon: Database, group: 'Trust & data' },
  { label: 'Data Ingestion', href: '/demo/ingestion', icon: UploadCloud, group: 'Trust & data' },
  { label: 'Metric Catalog', href: '/demo/metrics', icon: GitBranch, group: 'Trust & data' },
  { label: 'Reporting Center', href: '/demo/reports', icon: FileBarChart, group: 'Governance' },
  { label: 'Governance & audit', href: '/demo/governance', icon: BookOpen, group: 'Governance' },
  { label: 'Security Center', href: '/demo/security', icon: ShieldCheck, group: 'Governance' },
  { label: 'Operations Console', href: '/demo/operations', icon: Settings2, group: 'Governance' },
];

const workspaces = ['Northstar Retail Group', 'Crescent Commerce Co.', 'Atlas Distribution Demo'];

export function AppShell({ title, children }: Props) {
  const [palette, setPalette] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [workspaceMenu, setWorkspaceMenu] = useState(false);
  const [workspace, setWorkspace] = useState(workspaces[0]);
  const [query, setQuery] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [toast, setToast] = useState('');
  const results = useMemo(() => nav.filter((item) => item.label.toLowerCase().includes(query.toLowerCase())).slice(0, 8), [query]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPalette((open) => !open);
      }
      if (event.key === 'Escape') setPalette(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const demoAction = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 3200);
  };

  const grouped = ['Decision intelligence', 'Operations', 'Trust & data', 'Governance'];
  const sidebar = (
    <aside className="min-h-screen border-r border-line bg-[#141615] p-4">
      <Link href="/" className="mb-7 flex items-center gap-2 px-2 text-xl font-bold tracking-tight">
        <span className="grid h-6 w-6 place-items-center rounded border-2 border-signal"><Sparkles size={12}/></span>
        OpsLens AI
      </Link>
      <div className="relative mb-6">
        <button onClick={() => setWorkspaceMenu((value) => !value)} className="w-full rounded-lg border border-line bg-[#1b1e1c] p-3 text-left transition hover:border-[#4a574e]">
          <p className="label">Workspace</p><p className="mt-1 text-xs font-semibold">{workspace}</p><p className="mt-1 text-[10px] text-signal">● Synthetic demo workspace</p>
        </button>
        {workspaceMenu && <div className="absolute z-30 mt-1 w-full rounded-lg border border-line bg-[#202321] p-1 shadow-xl">{workspaces.map((name) => <button key={name} className="w-full rounded px-2 py-2 text-left text-xs hover:bg-[#2b302d]" onClick={() => { setWorkspace(name); setWorkspaceMenu(false); demoAction(`Workspace context changed to ${name} (demo UI).`); }}>{name}</button>)}</div>}
      </div>
      <button onClick={() => setPalette(true)} className="mb-5 flex w-full items-center justify-between rounded-md border border-line bg-[#1c201e] px-3 py-2 text-xs text-muted hover:text-ink"><span className="flex items-center gap-2"><Command size={14}/>Command palette</span><kbd className="rounded border border-[#3a403c] px-1.5 py-0.5 text-[9px]">⌘K</kbd></button>
      <nav className="space-y-4">{grouped.map((group) => <div key={group}><p className="mb-1 px-2 text-[9px] font-bold uppercase tracking-[.15em] text-[#697169]">{group}</p>{nav.filter((item) => item.group === group).map((item) => { const Icon = item.icon; return <Link href={item.href} key={item.label} className="flex items-center gap-3 rounded-md px-3 py-2 text-[12px] text-[#b8bcb6] transition hover:bg-[#252a27] hover:text-ink"><Icon size={15}/>{item.label}</Link>; })}</div>)}</nav>
      <p className="mt-8 text-[10px] leading-5 text-muted">Governed decision intelligence<br/>v0.2 · Multi-tenant demo mode</p>
    </aside>
  );

  return <div className="min-h-screen bg-canvas text-ink">
    <div className="hidden grid-cols-[252px_1fr] lg:grid">{sidebar}<main className="min-w-0 p-5 xl:p-8"><header className="mb-7 flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs text-muted">{workspace} / <span className="text-[#d6d3c8]">{title}</span></p><div className="mt-1 flex items-center gap-2"><span className="rounded border border-[#536b59] bg-[#1d2c22] px-2 py-1 text-[10px] text-[#a8d8b5]">Synthetic data</span><span className="rounded border border-[#4b4734] bg-[#2a291d] px-2 py-1 text-[10px] text-[#e3c986]">Inventory freshness delayed · 14h</span></div></div><div className="flex items-center gap-2"><button onClick={() => setPalette(true)} className="rounded-md border border-line bg-[#202421] p-2 text-muted hover:text-ink" aria-label="Open search"><Search size={16}/></button><div className="relative"><button onClick={() => setNotifications((value) => !value)} className="rounded-md border border-line bg-[#202421] p-2 text-muted hover:text-ink" aria-label="Open notifications"><Bell size={16}/></button>{notifications && <div className="absolute right-0 z-30 mt-2 w-72 rounded-lg border border-line bg-[#1b1e1c] p-3 shadow-xl"><p className="label">Notifications</p><p className="mt-3 text-xs"><span className="text-warning">Critical</span> · Scenario recommendation awaits organization approval.</p><p className="mt-3 border-t border-line pt-3 text-xs text-muted">2 data-quality notices are carried into inventory analysis.</p></div>}</div><button onClick={() => demoAction('Export queued in the synthetic workspace.')} className="rounded-md border border-line bg-[#262b28] px-3 py-2 text-xs">Export</button><button onClick={() => demoAction('Investigation draft opened in demo mode.')} className="rounded-md bg-[#e6e2d6] px-3 py-2 text-xs font-bold text-[#181a18]">Create investigation</button></div></header>{children}</main></div>
    <div className="lg:hidden"><header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-[#141615] p-4"><Link href="/" className="font-bold">OpsLens AI</Link><div className="flex gap-2"><button onClick={() => setPalette(true)} className="rounded border border-line p-2"><Search size={16}/></button><button onClick={() => setMobileOpen((v) => !v)} className="rounded border border-line p-2"><Menu size={16}/></button></div></header>{mobileOpen && <div className="border-b border-line bg-[#181b19] p-3"><div className="grid grid-cols-2 gap-1">{nav.slice(0,10).map((item) => <Link onClick={() => setMobileOpen(false)} href={item.href} key={item.label} className="rounded p-2 text-[11px] text-muted hover:bg-[#242925]">{item.label}</Link>)}</div></div>}<main className="p-4"><p className="mb-4 text-[10px] text-signal">{workspace} · Mobile executive mode</p>{children}</main></div>
    {palette && <div className="fixed inset-0 z-50 grid place-items-start bg-black/60 px-4 pt-[13vh]" onMouseDown={() => setPalette(false)}><div className="w-full max-w-xl overflow-hidden rounded-xl border border-[#4a504b] bg-[#171a18] shadow-2xl" onMouseDown={(event) => event.stopPropagation()}><div className="flex items-center gap-2 border-b border-line p-3"><Search size={17} className="text-muted"/><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search products, suppliers, alerts, reports, or actions…" className="w-full bg-transparent text-sm outline-none placeholder:text-[#727971]"/><button onClick={() => setPalette(false)} className="text-muted"><X size={17}/></button></div><div className="max-h-[360px] overflow-auto p-2"><p className="px-2 py-1 text-[9px] uppercase tracking-[.14em] text-muted">Commands & navigation</p>{results.length ? results.map((item) => { const Icon = item.icon; return <Link href={item.href} onClick={() => setPalette(false)} key={item.label} className="flex items-center justify-between rounded-lg px-3 py-3 hover:bg-[#242926]"><span className="flex items-center gap-3 text-sm"><Icon size={16} className="text-signal"/>{item.label}</span><span className="text-[10px] text-muted">{item.group}</span></Link> }) : <p className="p-5 text-sm text-muted">No result in the current workspace.</p>}</div></div></div>}
    {toast && <div className="fixed bottom-5 right-5 z-[60] max-w-sm rounded-lg border border-[#546858] bg-[#1c2a20] px-4 py-3 text-xs text-[#d9edda] shadow-xl">{toast}</div>}
  </div>;
}
