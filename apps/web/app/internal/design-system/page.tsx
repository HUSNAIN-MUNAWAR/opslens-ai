import { AppShell } from '../../../components/app-shell';

const states = ['Default', 'Loading', 'Success', 'Warning', 'Critical', 'Disabled', 'Empty', 'Error'];
const tokens = [
  ['Canvas', '#121413'], ['Surface', '#1c201e'], ['Border', '#303631'], ['Signal', '#8bd49b'], ['Warning', '#e3b35a'], ['Critical', '#ef7771'],
];

export default function DesignSystemPage() {
  return <AppShell title="Internal design system">
    <section className="mb-5">
      <h1 className="text-3xl font-bold tracking-tight">Internal design system</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">Phase 3 reusable components, status language, and visual tokens. This page is intentionally internal to the demo product.</p>
    </section>
    <div className="grid gap-3 lg:grid-cols-3">
      {tokens.map(([name, value]) => <article className="card p-4" key={name}>
        <div className="h-16 rounded border border-line" style={{ background: value }} />
        <p className="label mt-3">{name}</p>
        <p className="mt-1 text-xs text-muted">{value}</p>
      </article>)}
    </div>
    <div className="mt-4 grid gap-3 lg:grid-cols-2">
      {states.map((state) => <article className="card p-5" key={state}>
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">{state} component state</h2>
          <span className="chip">{state}</span>
        </div>
        <p className="mt-3 text-sm text-muted">Metric card, evidence card, approval timeline, source freshness indicator, and permission state share this status language.</p>
        <div className="mt-4 rounded border border-line bg-[#181c1a] p-3 text-xs">Focus-visible · keyboard reachable · color is paired with text labels.</div>
      </article>)}
    </div>
  </AppShell>;
}
