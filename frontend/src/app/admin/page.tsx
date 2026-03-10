'use client';
import { api } from '@/lib/api';
import { useEffect, useState } from 'react';

type JobRun = { id: number; job_name: string; status: string; processed_count: number; summary: string };
type ConnectorsResponse = { connectors?: string[] };

export default function AdminPage() {
  const [runs, setRuns] = useState<JobRun[]>([]);
  const [connectors, setConnectors] = useState<string[]>([]);
  const [error, setError] = useState('');

  const load = async () => {
    try {
      setError('');
      const [jobRuns, connectorPayload] = await Promise.all([
        api<JobRun[]>('/admin/jobs/runs'),
        api<ConnectorsResponse>('/admin/connectors'),
      ]);
      setRuns(jobRuns);
      setConnectors(Array.isArray(connectorPayload.connectors) ? connectorPayload.connectors : []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load admin data');
    }
  };

  useEffect(() => { load(); }, []);
  const runJob = async (j: string) => {
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
      await api(`/admin/connectors/${name}/run`, { method: 'POST', body: JSON.stringify({}) });
      await load();
    } catch (e: any) {
      setError(e?.message || `Failed to run connector ${name}`);
    }
  };

  return <div className='space-y-4'><h1 className='text-2xl font-bold'>Automation & Connectors</h1>
    {error && <div className='card text-red-700'>{error}</div>}
    <div>
      <h2 className='font-semibold mb-2'>Jobs</h2>
      {['ingest', 'rescore', 'strategy', 'stale'].map((j) => <button key={j} className='px-3 py-2 bg-slate-800 text-white rounded mr-2' onClick={() => runJob(j)}>Run {j}</button>)}
    </div>
    <div>
      <h2 className='font-semibold mb-2'>Connectors</h2>
      {connectors.map((name) => <button key={name} className='px-3 py-2 bg-indigo-700 text-white rounded mr-2 mb-2' onClick={() => runConnector(name)}>Run {name}</button>)}
    </div>
    <div className='card overflow-auto'>
      <h2 className='font-semibold mb-2'>Recent Job Runs</h2>
      <table className='w-full text-sm'><thead><tr><th className='text-left'>Job</th><th>Status</th><th>Processed</th><th className='text-left'>Summary</th></tr></thead><tbody>{runs.map((r) => <tr key={r.id} className='border-t'><td>{r.job_name}</td><td>{r.status}</td><td>{r.processed_count}</td><td>{r.summary}</td></tr>)}</tbody></table>
    </div>
  </div>
}
