'use client';
import { api } from '@/lib/api';
import { useEffect, useState } from 'react';

export default function AdminPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [error, setError] = useState('');

  const load = async () => {
    try {
      setError('');
      setRuns(await api('/admin/jobs/runs'));
    } catch (e: any) {
      setError(e?.message || 'Failed to load job runs');
    }
  };

  useEffect(() => { load(); }, []);
  const run = async (j: string) => {
    try {
      setError('');
      await api(`/admin/jobs/${j}`, { method: 'POST' });
      await load();
    } catch (e: any) {
      setError(e?.message || `Failed to run ${j}`);
    }
  };

  return <div className='space-y-4'><h1 className='text-2xl font-bold'>Automation Jobs</h1>
    {error && <div className='card text-red-700'>{error}</div>}
    <div>{['ingest', 'rescore', 'strategy', 'stale'].map((j) => <button key={j} className='px-3 py-2 bg-slate-800 text-white rounded mr-2' onClick={() => run(j)}>Run {j}</button>)}</div>
    <div className='card overflow-auto'>
      <h2 className='font-semibold mb-2'>Recent Job Runs</h2>
      <table className='w-full text-sm'><thead><tr><th className='text-left'>Job</th><th>Status</th><th>Processed</th><th className='text-left'>Summary</th></tr></thead><tbody>{runs.map((r) => <tr key={r.id} className='border-t'><td>{r.job_name}</td><td>{r.status}</td><td>{r.processed_count}</td><td>{r.summary}</td></tr>)}</tbody></table>
    </div>
  </div>
}
