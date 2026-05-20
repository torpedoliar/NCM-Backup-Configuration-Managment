import { useEffect } from 'react';
import { useLiveEvents } from '../store/live-events';
import type { LiveEvent } from '../api/types';

export function openLiveSocket(token: string, onEvent: (event: LiveEvent) => void): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${proto}//${window.location.host}/ws?token=${encodeURIComponent(token)}`);
  socket.onmessage = (message) => {
    try {
      const data: unknown = JSON.parse(message.data);
      if (data && typeof data === 'object' && 'type' in data && 'ts' in data) {
        useLiveEvents.getState().push(data as LiveEvent);
        onEvent(data as LiveEvent);
      }
    } catch {
      // ignore malformed frames
    }
  };
  return socket;
}

export function useLiveSocket(token: string | null) {
  const push = useLiveEvents((state) => state.push);
  useEffect(() => {
    if (!token) return;
    const socket = openLiveSocket(token, push);
    return () => {
      socket.close();
    };
  }, [token, push]);
}
