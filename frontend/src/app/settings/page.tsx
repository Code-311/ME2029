'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export default function SettingsPage() {
  const [profile, setProfile] = useState<any>(null);
  const [flags, setFlags] = useState<any>({});
  const [weights, setWeights] = useState<Record<string, number>>({});

  useEffect(() => {
    (async () => {
      setProfile(await api('/profile'));
      setFlags(await api('/settings/flags'));
      setWeights(await api('/settings/weights'));
    })();
  }, []);

  if (!profile) return <div>Loading...</div>;

  return <div className='space-y-4'><h1 className='text-2xl font-bold'>Profile & Scoring Settings</h1>
    <div className='card'>
      <label className='text-sm text-slate-600'>Headline</label>
      <input className='border p-2 w-full mt-1' value={profile.headline} onChange={(e) => setProfile({ ...profile, headline: e.target.value })} />
      <button className='mt-2 px-3 py-2 bg-slate-800 text-white rounded' onClick={() => api('/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profile) })}>Save Profile</button>
    </div>
    <div className='card'><h2 className='font-semibold mb-2'>Scoring Weights</h2>{Object.entries(weights).map(([k, v]) => <div key={k} className='mb-2'><label className='text-sm'>{k}</label><input type='number' step='0.01' className='border p-2 w-full' value={v} onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })} /></div>)}
      <button className='px-3 py-2 bg-slate-800 text-white rounded' onClick={() => api('/settings/weights', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(weights) })}>Save Weights</button>
    </div>
    <div className='card'>LLM Strategy Enabled: <input type='checkbox' checked={flags.use_llm_strategy || false} onChange={async (e) => { const f = { ...flags, use_llm_strategy: e.target.checked }; setFlags(f); await api('/settings/flags', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(f) }); }} /></div>
  </div>
}
