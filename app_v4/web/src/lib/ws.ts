import { useEffect } from 'react';
import { useLiveEvents } from '../store/live-events';
import type { LiveEvent } from '../api/types';

export function openLiveSocket(token: string): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${proto}//${window.location.host}/ws?token=${encodeURIComponent(token)}`);
  socket.onmessage = (message) => {
    try {
      const data: unknown = JSON.parse(message.data);
      if (data && typeof data === 'object' && 'type' in data && 'ts' in data) {
        useLiveEvents.getState().push(data as LiveEvent);
      }
    } catch {
      // ignore malformed frames
    }
  };
  return socket;
}

export function useLiveSocket(token: string | null) {
  useEffect(() => {
    if (!token) return;
    const socket = openLiveSocket(token);
    return () => {
      socket.close();
    };
  }, [token]);
}
