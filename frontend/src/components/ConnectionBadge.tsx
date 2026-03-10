export function ConnectionBadge({ status }: { status: 'connecting' | 'connected' | 'reconnecting' }) {
  const map = {
    connecting: 'bg-amber-100 text-amber-700',
    connected: 'bg-emerald-100 text-emerald-700',
    reconnecting: 'bg-orange-100 text-orange-700',
  } as const;
  return <span className={`px-2 py-1 rounded text-xs font-medium ${map[status]}`}>Realtime: {status}</span>;
}
