import { useEffect } from 'react';
import { useLiveActivity } from '../store/liveActivity';
import type { LiveEvent } from '../api/types';

export function openLiveSocket(token: string, onEvent: (event: LiveEvent) => void): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${proto}//${window.location.host}/ws?token=${encodeURIComponent(token)}`);
  socket.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as LiveEvent);
    } catch {
      // ignore malformed frames
    }
  };
  return socket;
}

export function useLiveSocket(token: string | null) {
  const push = useLiveActivity((state) => state.push);
  useEffect(() => {
    if (!token) return;
    const socket = openLiveSocket(token, push);
    return () => {
      socket.close();
    };
  }, [token, push]);
}
