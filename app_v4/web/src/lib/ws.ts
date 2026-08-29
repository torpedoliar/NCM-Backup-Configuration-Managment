import { useEffect } from 'react';
import { useLiveEvents } from '../store/live-events';
import type { LiveEvent } from '../api/types';

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_DELAY_MS = 30000;

export function openLiveSocket(token: string): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${proto}//${window.location.host}/ws?token=${encodeURIComponent(token)}`);
  socket.onmessage = (message) => {
    try {
      const data: unknown = JSON.parse(message.data);
      if (data && typeof data === 'object' && 'type' in data && 'ts' in data) {
        const event = data as LiveEvent;
        // The server sends a 'connected' handshake frame on accept; it is not
        // an activity event and must not pollute the live feed or 24h counter.
        if (event.type === 'connected') return;
        useLiveEvents.getState().push(event);
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
    let socket: WebSocket | null = null;
    let closed = false;
    let retryDelay = RECONNECT_DELAY_MS;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      socket = openLiveSocket(token);
      socket.onclose = () => {
        if (closed) return;
        // Back off on repeated failures so a dead backend doesn't spin.
        retryTimer = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, MAX_RECONNECT_DELAY_MS);
      };
      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close();
    };
  }, [token]);
}
