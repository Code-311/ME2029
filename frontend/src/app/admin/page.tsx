'use client';
import { api } from '@/lib/api';
import { useEffect, useState } from 'react';

type Connector = { name: string; configured: boolean };

export default function AdminPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [outcomes, setOutcomes] = useState<any[]>([]);
  const [error, setError] = useState('');

  const load = async () => {
    try {
      setError('');
      const [jobRuns, connectorList, connectorOutcomes] = await Promise.all([
        api<any[]>('/admin/jobs/runs'),
        api<Connector[]>('/admin/connectors'),
        api<any[]>('/admin/connectors/outcomes'),
      ]);
      setRuns(jobRuns);
      setConnectors(connectorList);
      setOutcomes(connectorOutcomes);
    } catch (e: any) {
      setError(e?.message || 'Failed to load admin data');
    }
  };

  useEffect(() => {
    load();
  }, []);

  const run = async (j: string) => {
    try {
      setError('');
      await api(`/admin/jobs/${j}`, { method: 'POST' });
      await load();
    } catch (e: any) {
      setError(e?.message || `Failed to run ${j}`);
    }
  };

  const runConnector = async (name: string) => {
    try {
      setError('');
      await api(`/admin/connectors/${name}/run`, { method: 'POST', body: '{}' });
      await load();
    } catch (e: any) {
      setError(e?.message || `Failed to run connector ${name}`);
    }
  };

  return <div className='space-y-4'><h1 className='text-2xl font-bold'>Automation Jobs</h1>
    {error && <div className='card text-red-700'>{error}</div>}
    <div>{['ingest', 'rescore', 'strategy', 'stale'].map((j) => <button key={j} className='px-3 py-2 bg-slate-800 text-white rounded mr-2' onClick={() => run(j)}>Run {j}</button>)}</div>
    <div className='card overflow-auto'>
      <h2 className='font-semibold mb-2'>Connectors</h2>
      <table className='w-full text-sm'><thead><tr><th className='text-left'>Name</th><th>Configured</th><th></th></tr></thead><tbody>{connectors.map((c) => <tr key={c.name} className='border-t'><td>{c.name}</td><td>{String(c.configured)}</td><td><button className='px-2 py-1 bg-slate-700 text-white rounded' onClick={() => runConnector(c.name)}>Run</button></td></tr>)}</tbody></table>
    </div>
    <div className='card overflow-auto'>
      <h2 className='font-semibold mb-2'>Recent Connector Outcomes</h2>
      <table className='w-full text-sm'><thead><tr><th className='text-left'>Job</th><th>Status</th><th>Processed</th><th className='text-left'>Summary</th></tr></thead><tbody>{outcomes.map((r) => <tr key={r.id} className='border-t'><td>{r.job_name}</td><td>{r.status}</td><td>{r.processed_count}</td><td>{r.summary}</td></tr>)}</tbody></table>
    </div>
    <div className='card overflow-auto'>
      <h2 className='font-semibold mb-2'>Recent Job Runs</h2>
      <table className='w-full text-sm'><thead><tr><th className='text-left'>Job</th><th>Status</th><th>Processed</th><th className='text-left'>Summary</th></tr></thead><tbody>{runs.map((r) => <tr key={r.id} className='border-t'><td>{r.job_name}</td><td>{r.status}</td><td>{r.processed_count}</td><td>{r.summary}</td></tr>)}</tbody></table>
    </div>
  </div>;
}
