'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';

interface PlanItem {
  id: number;
  period_type: string;
  title: string;
  details: string;
  completed: boolean;
}

interface Recommendation {
  id: number;
  recommendation_type: string;
  urgency: string;
  title: string;
  suggested_action: string;
}

export default function ExecutionPage() {
  const [plans, setPlans] = useState<PlanItem[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const load = useCallback(async () => {
    const [p, r] = await Promise.all([
      api<PlanItem[]>('/plans'),
      api<Recommendation[]>('/recommendations?status=open'),
    ]);
    setPlans(p);
    setRecommendations(r);
  }, []);
  useEffect(() => { load(); }, [load]);
  const toggle = async (id: number) => { await api(`/plans/${id}/toggle`, { method: 'PATCH' }); load(); };

  const weekly = useMemo(() => plans.filter((p) => p.period_type === 'weekly'), [plans]);
  const monthly = useMemo(() => plans.filter((p) => p.period_type === 'monthly'), [plans]);
  const actionable = useMemo(() => recommendations.filter((r) => ['NETWORK_ACTION', 'FOLLOW_UP_ACTION'].includes(r.recommendation_type)).slice(0, 8), [recommendations]);

  return <div className='space-y-4'><h1 className='text-2xl font-bold'>Execution Plan</h1>
    <button className='px-3 py-2 bg-slate-800 text-white rounded' onClick={async () => { await api('/plans/regenerate', { method: 'POST' }); load(); }}>Regenerate Plan</button>
    <div className='grid md:grid-cols-2 gap-4'>
      <div className='card'><h2 className='font-semibold mb-2'>Weekly Micro-Actions</h2>{weekly.map((p) => <div className='border-b py-2' key={p.id}><div className='font-medium'>{p.title}</div><div className='text-sm text-slate-600'>{p.details}</div><button className='text-blue-600 text-sm' onClick={() => toggle(p.id)}>{p.completed ? 'Mark open' : 'Mark done'}</button></div>)}</div>
      <div className='card'><h2 className='font-semibold mb-2'>Monthly Strategic Reviews</h2>{monthly.map((p) => <div className='border-b py-2' key={p.id}><div className='font-medium'>{p.title}</div><div className='text-sm text-slate-600'>{p.details}</div><button className='text-blue-600 text-sm' onClick={() => toggle(p.id)}>{p.completed ? 'Mark open' : 'Mark done'}</button></div>)}</div>
    </div>
    <div className='card'><h2 className='font-semibold mb-2'>Decision Engine Actions</h2>{actionable.map((r) => <div className='border-b py-2' key={r.id}><div className='font-medium'>{r.title}</div><div className='text-sm text-slate-600'>{r.suggested_action}</div><div className='text-xs text-slate-500'>{r.recommendation_type} · {r.urgency}</div></div>)}</div>
  </div>
}
