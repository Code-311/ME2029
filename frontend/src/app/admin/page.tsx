'use client';
import { api } from '@/lib/api';
import { useEffect, useState } from 'react';

interface JobRun {
  id: number;
  job_name: string;
  status: string;
  processed_count: number;
  summary: string;
}

interface CompanySignal {
  id: number;
  company_id: number;
  signal_type: string;
  severity: string;
  title: string;
}

interface Recommendation {
  id: number;
  recommendation_type: string;
  urgency: string;
  decision_score: number;
  title: string;
}

export default function AdminPage() {
  const [runs, setRuns] = useState<JobRun[]>([]);
  const [error, setError] = useState('');
  const [companySignals, setCompanySignals] = useState<CompanySignal[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);

  const load = async () => {
    try {
      setError('');
      const [r, cs, recs] = await Promise.all([
        api<JobRun[]>('/admin/jobs/runs'),
        api<CompanySignal[]>('/company-signals'),
        api<Recommendation[]>('/recommendations?status=open'),
      ]);
      setRuns(r);
      setCompanySignals(cs);
      setRecommendations(recs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load job runs');
    }
  };

  useEffect(() => { load(); }, []);
  const run = async (j: string) => {
    try {
      setError('');
      await api(`/admin/jobs/${j}`, { method: 'POST' });
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `Failed to run ${j}`);
    }
  };

  return <div className='space-y-4'><h1 className='text-2xl font-bold'>Automation Jobs</h1>
    {error && <div className='card text-red-700'>{error}</div>}
    <div>{['ingest', 'rescore', 'strategy', 'stale', 'company_intelligence', 'decision_engine'].map((j) => <button key={j} className='px-3 py-2 bg-slate-800 text-white rounded mr-2' onClick={() => run(j)}>Run {j}</button>)}</div>
    <div className='card overflow-auto'>
      <h2 className='font-semibold mb-2'>Recent Job Runs</h2>
      <table className='w-full text-sm'><thead><tr><th className='text-left'>Job</th><th>Status</th><th>Processed</th><th className='text-left'>Summary</th></tr></thead><tbody>{runs.map((r) => <tr key={r.id} className='border-t'><td>{r.job_name}</td><td>{r.status}</td><td>{r.processed_count}</td><td>{r.summary}</td></tr>)}</tbody></table>
    </div>
    <div className='card overflow-auto'>
      <h2 className='font-semibold mb-2'>Latest Company Signals</h2>
      <table className='w-full text-sm'><thead><tr><th className='text-left'>Company ID</th><th>Type</th><th>Severity</th><th className='text-left'>Title</th></tr></thead><tbody>{companySignals.slice(0, 20).map((s) => <tr key={s.id} className='border-t'><td>{s.company_id}</td><td>{s.signal_type}</td><td>{s.severity}</td><td>{s.title}</td></tr>)}</tbody></table>
    </div>
    <div className='card overflow-auto'>
      <h2 className='font-semibold mb-2'>Open Recommendations</h2>
      <table className='w-full text-sm'><thead><tr><th className='text-left'>Type</th><th>Urgency</th><th>Score</th><th className='text-left'>Title</th></tr></thead><tbody>{recommendations.slice(0, 20).map((r) => <tr key={r.id} className='border-t'><td>{r.recommendation_type}</td><td>{r.urgency}</td><td>{r.decision_score}</td><td>{r.title}</td></tr>)}</tbody></table>
      <button className='mt-3 px-3 py-2 bg-slate-700 text-white rounded' onClick={async () => { await api('/recommendations/refresh', { method: 'POST' }); await load(); }}>Refresh recommendations</button>
    </div>
  </div>
}
