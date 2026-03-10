'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { useRealtime } from '@/hooks/useRealtime';
import { ConnectionBadge } from '@/components/ConnectionBadge';

export default function Dashboard() {
  const [opps, setOpps] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [nodes, setNodes] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setError('');
      const [o, p, n, s] = await Promise.all([
      api<any[]>('/opportunities'),
      api<any[]>('/plans'),
      api<any[]>('/nodes'),
      api<any[]>('/signals'),
    ]);
    setOpps(o);
    setPlans(p);
    setNodes(n);
      setSignals(s);
    } catch (e: any) {
      setError(e?.message || 'Failed to load dashboard');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const rt = useRealtime(load);
  const topActions = useMemo(() => plans.filter((p) => !p.completed).slice(0, 4), [plans]);
  const byStage = opps.reduce((a, o) => {
    a[o.status] = (a[o.status] || 0) + 1;
    return a;
  }, {} as Record<string, number>);

  return (
    <div className='space-y-4'>
      <div className='flex items-center justify-between'>
        <h1 className='text-2xl font-bold'>Career Radar Overview</h1>
        <ConnectionBadge status={rt} />
      </div>
      {error && <div className='card text-red-700'>{error}</div>}
      <div className='grid grid-cols-1 md:grid-cols-4 gap-4'>
        <div className='card'><div className='text-slate-500 text-sm'>Qualified Pipeline</div><div className='text-2xl font-semibold'>{opps.length}</div></div>
        <div className='card'><div className='text-slate-500 text-sm'>Average Score</div><div className='text-2xl font-semibold'>{(opps.reduce((a, b) => a + b.score_total, 0) / (opps.length || 1)).toFixed(2)}</div></div>
        <div className='card'><div className='text-slate-500 text-sm'>Active Network Nodes</div><div className='text-2xl font-semibold'>{nodes.length}</div></div>
        <div className='card'><div className='text-slate-500 text-sm'>Open Signals</div><div className='text-2xl font-semibold'>{signals.length}</div></div>
      </div>
      <div className='grid md:grid-cols-2 gap-4'>
        <div className='card'>
          <h2 className='font-semibold mb-2'>Opportunities by Stage</h2>
          <div className='space-y-1 text-sm'>{Object.entries(byStage).map(([k, v]) => <div key={k} className='flex justify-between'><span>{k}</span><span>{v}</span></div>)}</div>
        </div>
        <div className='card'>
          <h2 className='font-semibold mb-2'>Top Next Actions</h2>
          <ul className='space-y-2 text-sm'>{topActions.map((p) => <li key={p.id}><span className='font-medium'>{p.title}</span><div className='text-slate-600'>{p.due_label}</div></li>)}</ul>
        </div>
      </div>
      <div className='card'>
        <h2 className='font-semibold mb-2'>Recent Signals</h2>
        <div className='space-y-2 text-sm'>{signals.slice(0, 5).map((s) => <div key={s.id}><span className='font-medium'>{s.title}</span><div className='text-slate-600'>{s.details}</div></div>)}</div>
      </div>
    </div>
  );
}
