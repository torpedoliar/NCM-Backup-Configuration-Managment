import { describe, expect, it, beforeEach, vi } from 'vitest';
import { useLiveEvents } from '../store/live-events';
import { openLiveSocket } from './ws';
import type { LiveEvent } from '../api/types';

class FakeWebSocket {
  onmessage: ((message: { data: string }) => void) | null = null;
  close = vi.fn();
  constructor(public url: string) {}
}

describe('openLiveSocket', () => {
  beforeEach(() => {
    useLiveEvents.getState().clear();
    (globalThis as { WebSocket?: typeof WebSocket }).WebSocket = FakeWebSocket as unknown as typeof WebSocket;
  });

  it('pushes each parsed event into the store exactly once', () => {
    const socket = openLiveSocket('token') as unknown as FakeWebSocket;
    const event: LiveEvent = { type: 'backup_completed', payload: {}, ts: '2026-05-20T01:00:00Z' };
    socket.onmessage?.({ data: JSON.stringify(event) });
    expect(useLiveEvents.getState().events).toHaveLength(1);
    expect(useLiveEvents.getState().events[0]).toEqual(event);
  });

  it('ignores frames missing type or ts', () => {
    const socket = openLiveSocket('token') as unknown as FakeWebSocket;
    socket.onmessage?.({ data: JSON.stringify({ type: 'x' }) });
    socket.onmessage?.({ data: JSON.stringify({ ts: 'now' }) });
    socket.onmessage?.({ data: 'not-json' });
    expect(useLiveEvents.getState().events).toHaveLength(0);
  });
});
