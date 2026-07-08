'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, RefreshCw, ShieldAlert } from 'lucide-react';
import { apiFetch, summarizeJson, type JsonValue } from '../lib/api-client';

type Mutation = {
  label: string;
  path: string;
  method?: 'POST' | 'PATCH' | 'DELETE';
  body?: JsonValue;
};

type Props = {
  title: string;
  endpoint: string;
  summary: string;
  mutations?: Mutation[];
};

function countRecords(data: JsonValue | null) {
  if (Array.isArray(data)) return data.length;
  if (data && typeof data === 'object') {
    const object = data as Record<string, JsonValue>;
    if (Array.isArray(object.alerts)) return object.alerts.length;
    if (Array.isArray(object.issues)) return object.issues.length;
    if (Array.isArray(object.kpis)) return object.kpis.length;
    if (Array.isArray(object.scenarios)) return object.scenarios.length;
    if (Array.isArray(object.health)) return object.health.length;
  }
  return 1;
}

export function ApiWorkflowPanel({ title, endpoint, summary, mutations = [] }: Props) {
  const [data, setData] = useState<JsonValue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastAction, setLastAction] = useState<string>('Initial live read');

  const load = useCallback(async () => {
    setLoading(true);
    const result = await apiFetch(endpoint);
    setData(result.data);
    setError(result.error);
    setRequestId(result.requestId);
    setLoading(false);
  }, [endpoint]);

  useEffect(() => { void load(); }, [load]);

  const health = useMemo(() => {
    if (error) return { label: 'Degraded API state', tone: 'text-warning', icon: ShieldAlert };
    if (loading) return { label: 'Loading live API state', tone: 'text-muted', icon: RefreshCw };
    return { label: 'Live API state', tone: 'text-signal', icon: CheckCircle2 };
  }, [error, loading]);
  const Icon = health.icon;

  const runMutation = async (mutation: Mutation) => {
    setLastAction(`Running: ${mutation.label}`);
    const result = await apiFetch(mutation.path, { method: mutation.method ?? 'POST', body: mutation.body ? JSON.stringify(mutation.body) : undefined });
    setRequestId(result.requestId);
    if (result.error) {
      setError(result.error);
      setLastAction(`${mutation.label} failed`);
      return;
    }
    setError(null);
    setLastAction(`${mutation.label} completed and audit state was updated where applicable.`);
    await load();
  };

  return <section className="card mt-4 p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="label">Phase 3 API-driven workflow</p>
        <h2 className="mt-1 text-lg font-semibold">{title}</h2>
        <p className="mt-1 max-w-3xl text-xs leading-5 text-muted">{summary}</p>
      </div>
      <span className={`inline-flex items-center gap-2 rounded-md border border-line bg-[#1d211f] px-3 py-2 text-[10px] ${health.tone}`}><Icon size={14}/>{health.label}</span>
    </div>
    <div className="mt-4 grid gap-3 lg:grid-cols-[.75fr_1.25fr]">
      <div className="rounded-lg border border-line bg-[#181c1a] p-4">
        <p className="label">Operational feedback</p>
        <p className="mt-2 text-sm font-semibold">{loading ? 'Reading backend state…' : error ? 'Actionable degraded state' : `${countRecords(data)} live record signal(s) loaded`}</p>
        <p className="mt-2 text-xs leading-5 text-muted">{error ?? lastAction}</p>
        {requestId && <p className="mt-3 rounded border border-[#3d463f] bg-[#202421] px-2 py-1 text-[10px] text-muted">Request ID: {requestId}</p>}
        <div className="mt-4 flex flex-wrap gap-2">{mutations.map((mutation) => <button key={mutation.label} onClick={() => void runMutation(mutation)} className="rounded-md border border-line px-3 py-2 text-xs text-[#d9d7ce] hover:border-[#55705c]">{mutation.label}</button>)}<button onClick={() => void load()} className="rounded-md bg-[#e6e2d6] px-3 py-2 text-xs font-bold text-[#181a18]">Refresh</button></div>
      </div>
      <pre className="max-h-80 overflow-auto rounded-lg border border-line bg-canvas p-4 text-[10px] leading-5 text-[#d8e5d9]">{loading ? 'Loading typed API payload…' : error ? `Error: ${error}` : summarizeJson(data)}</pre>
    </div>
  </section>;
}
