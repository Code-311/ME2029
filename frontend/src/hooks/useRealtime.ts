'use client';
import { useEffect, useRef, useState } from 'react';
import { API } from '@/lib/api';

export function useRealtime(onEvent: () => void) {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'reconnecting'>('connecting');
  const lastVersion = useRef<number>(-1);

  useEffect(() => {
    let source: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      if (closed) return;
      setStatus(lastVersion.current < 0 ? 'connecting' : 'reconnecting');
      source = new EventSource(`${API}/events/stream`);
      source.onopen = () => setStatus('connected');
      source.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (typeof data.version === 'number' && data.version > lastVersion.current) {
            lastVersion.current = data.version;
            onEvent();
          }
        } catch {
          onEvent();
        }
      };
      source.onerror = () => {
        if (closed) return;
        setStatus('reconnecting');
        source?.close();
        if (!retryTimer) {
          retryTimer = setTimeout(() => {
            retryTimer = null;
            connect();
          }, 2000);
        }
      };
    };

    connect();
    return () => {
      closed = true;
      source?.close();
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [onEvent]);

  return status;
}
