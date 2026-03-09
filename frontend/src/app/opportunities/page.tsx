'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRealtime } from '@/hooks/useRealtime';
import { ConnectionBadge } from '@/components/ConnectionBadge';

export default function OpportunitiesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [q, setQ] = useState('');
  const [sortBy, setSortBy] = useState<'score_total' | 'discovered_at'>('score_total');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [signalFilter, setSignalFilter] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setError('');
      const query = new URLSearchParams({ sort_by: sortBy, sort_dir: sortDir });
    if (signalFilter) query.set('signal_type', signalFilter);
    const [o, s] = await Promise.all([api<any[]>(`/opportunities?${query.toString()}`), api<any[]>('/signals')]);
    setItems(o);
      setSignals(s);
    } catch (e: any) {
      setError(e?.message || 'Failed to load opportunities');
    }
  }, [sortBy, sortDir, signalFilter]);

  useEffect(() => { load(); }, [load]);
  const rt = useRealtime(load);

  const signalTypes = useMemo(() => Array.from(new Set(signals.map((s) => s.signal_type))), [signals]);
  const signalMap = useMemo(() => signals.reduce((acc, s) => { (acc[s.opportunity_id] ||= []).push(s); return acc; }, {} as Record<number, any[]>), [signals]);
  const filtered = items.filter((i) => `${i.company} ${i.role_title}`.toLowerCase().includes(q.toLowerCase()));

  return <div className='space-y-4'>
    <div className='flex items-center justify-between'><h1 className='text-2xl font-bold'>Opportunities</h1><ConnectionBadge status={rt} /></div>
    {error && <div className='card text-red-700'>{error}</div>}
    <div className='flex gap-2 flex-wrap'>
      <input className='border p-2 rounded' placeholder='Search company or role' value={q} onChange={(e) => setQ(e.target.value)} />
      <select className='border p-2 rounded' value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}><option value='score_total'>Sort: Score</option><option value='discovered_at'>Sort: Newest</option></select>
      <select className='border p-2 rounded' value={sortDir} onChange={(e) => setSortDir(e.target.value as any)}><option value='desc'>Desc</option><option value='asc'>Asc</option></select>
      <select className='border p-2 rounded' value={signalFilter} onChange={(e) => setSignalFilter(e.target.value)}><option value=''>All signals</option>{signalTypes.map((t) => <option key={t} value={t}>{t}</option>)}</select>
    </div>
    <div className='card overflow-auto'>
      <table className='w-full text-sm'>
        <thead><tr><th className='text-left'>Company</th><th className='text-left'>Role</th><th>Score</th><th>Status</th><th className='text-left'>Signals</th></tr></thead>
        <tbody>{filtered.map((i) => <tr key={i.id} className='border-t align-top'><td><Link className='text-blue-600 font-medium' href={`/opportunities/${i.id}`}>{i.company}</Link></td><td>{i.role_title}</td><td className='text-center'>{i.score_total}</td><td className='text-center'>{i.status}</td><td>{(signalMap[i.id] || []).slice(0, 2).map((s) => <span key={s.id} className='inline-block mr-1 mb-1 px-2 py-0.5 rounded bg-slate-100'>{s.signal_type}</span>)}</td></tr>)}</tbody>
      </table>
    </div>
  </div>
}
