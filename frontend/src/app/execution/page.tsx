'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';

export default function ExecutionPage() {
  const [plans, setPlans] = useState<any[]>([]);
  const load = useCallback(async () => setPlans(await api('/plans')), []);
  useEffect(() => { load(); }, [load]);
  const toggle = async (id: number) => { await api(`/plans/${id}/toggle`, { method: 'PATCH' }); load(); };

  const weekly = useMemo(() => plans.filter((p) => p.period_type === 'weekly'), [plans]);
  const monthly = useMemo(() => plans.filter((p) => p.period_type === 'monthly'), [plans]);

  return <div className='space-y-4'><h1 className='text-2xl font-bold'>Execution Plan</h1>
    <button className='px-3 py-2 bg-slate-800 text-white rounded' onClick={async () => { await api('/plans/regenerate', { method: 'POST' }); load(); }}>Regenerate Plan</button>
    <div className='grid md:grid-cols-2 gap-4'>
      <div className='card'><h2 className='font-semibold mb-2'>Weekly Micro-Actions</h2>{weekly.map((p) => <div className='border-b py-2' key={p.id}><div className='font-medium'>{p.title}</div><div className='text-sm text-slate-600'>{p.details}</div><button className='text-blue-600 text-sm' onClick={() => toggle(p.id)}>{p.completed ? 'Mark open' : 'Mark done'}</button></div>)}</div>
      <div className='card'><h2 className='font-semibold mb-2'>Monthly Strategic Reviews</h2>{monthly.map((p) => <div className='border-b py-2' key={p.id}><div className='font-medium'>{p.title}</div><div className='text-sm text-slate-600'>{p.details}</div><button className='text-blue-600 text-sm' onClick={() => toggle(p.id)}>{p.completed ? 'Mark open' : 'Mark done'}</button></div>)}</div>
    </div>
  </div>
}
