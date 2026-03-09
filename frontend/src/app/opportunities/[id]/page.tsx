'use client';
import { api } from '@/lib/api';
import { useEffect, useState } from 'react';

export default function OpportunityDetail({ params }: { params: { id: string } }) {
  const [opp, setOpp] = useState<any>();
  const [nodes, setNodes] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        setError('');
        setOpp(await api(`/opportunities/${params.id}`));
        setNodes(await api(`/opportunities/${params.id}/network-recommendations`));
        setSignals(await api(`/opportunities/${params.id}/signals`));
      } catch (e: any) {
        setError(e?.message || 'Failed to load opportunity');
      }
    })();
  }, [params.id]);

  if (error) return <div className='card text-red-700'>{error}</div>;
  if (!opp) return <div>Loading...</div>;

  return <div className='space-y-4'>
    <h1 className='text-2xl font-bold'>{opp.role_title} @ {opp.company}</h1>
    <div className='grid md:grid-cols-3 gap-4'>
      <div className='card'><div className='text-sm text-slate-500'>Score</div><div className='text-3xl font-semibold'>{opp.score_total}</div></div>
      <div className='card'><div className='text-sm text-slate-500'>Location</div><div>{opp.location}</div></div>
      <div className='card'><div className='text-sm text-slate-500'>Compensation</div><div>{opp.estimated_compensation}</div></div>
    </div>
    <div className='card'><h2 className='font-semibold mb-2'>Score Explanation</h2><p>{opp.score_explanation}</p></div>
    <div className='card'><h2 className='font-semibold mb-2'>Factor Breakdown</h2>
      <div className='space-y-2 text-sm'>{(opp.score_breakdown?.factors || []).map((f: any) => <div key={f.name} className='border rounded p-2'><div className='flex justify-between'><span className='font-medium'>{f.name}</span><span>{f.raw_score}/10 × {f.weight}</span></div><div className='text-slate-600'>{f.reason}</div></div>)}</div>
    </div>
    <div className='card'><h2 className='font-semibold mb-2'>Signals</h2>{signals.length === 0 ? <div className='text-sm text-slate-500'>No active signals.</div> : signals.map((s) => <div key={s.id} className='mb-2'><div className='font-medium'>{s.title}</div><div className='text-sm text-slate-600'>{s.details}</div></div>)}</div>
    <div className='card'><h2 className='font-semibold mb-2'>Recommended Network Entry Points</h2>{nodes.length === 0 ? <div className='text-sm text-slate-500'>No linked network nodes yet.</div> : nodes.map((n) => <div key={n.id}>{n.full_name} — {n.node_role_type} (Influence {n.influence_score}, Access {n.accessibility_score})</div>)}</div>
  </div>;
}
