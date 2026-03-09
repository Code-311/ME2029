'use client';
import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';

export default function NetworkPage() {
  const [companies, setCompanies] = useState<any[]>([]);
  const [nodes, setNodes] = useState<any[]>([]);
  const [companySignals, setCompanySignals] = useState<any[]>([]);
  const [role, setRole] = useState('');
  useEffect(() => { (async () => { const [c, n, cs] = await Promise.all([api('/companies'), api('/nodes'), api('/company-signals')]); setCompanies(c); setNodes(n); setCompanySignals(cs); })(); }, []);

  const roleTypes = useMemo(() => Array.from(new Set(nodes.map((n) => n.node_role_type))), [nodes]);

  return <div className='space-y-4'><h1 className='text-2xl font-bold'>Network Intelligence</h1>
    <select className='border p-2 rounded' value={role} onChange={(e) => setRole(e.target.value)}><option value=''>All role types</option>{roleTypes.map((r) => <option key={r} value={r}>{r}</option>)}</select>
    {companies.map((c) => {
      const companyNodes = nodes
        .filter((n) => n.company_id === c.id)
        .filter((n) => !role || n.node_role_type === role)
        .sort((a, b) => (b.influence_score + b.accessibility_score) - (a.influence_score + a.accessibility_score));
      const signals = companySignals.filter((s) => s.company_id === c.id).slice(0, 3);
      return <div className='card' key={c.id}><h2 className='font-semibold'>{c.name}</h2><div className='text-sm text-slate-500 mb-2'>{c.industry}</div>{companyNodes.map((n) => <div key={n.id} className='border-t py-2'><div className='font-medium'>{n.full_name} — {n.role_title}</div><div className='text-sm text-slate-600'>{n.node_role_type} · Influence {n.influence_score} · Access {n.accessibility_score} · Relationship {n.relationship_strength}</div></div>)}{signals.length > 0 && <div className='border-t pt-2 mt-2'><div className='text-sm font-medium'>Company Signals</div>{signals.map((s) => <div key={s.id} className='text-sm text-slate-600'>{s.signal_type}: {s.title}</div>)}</div>}</div>;
    })}
  </div>
}
