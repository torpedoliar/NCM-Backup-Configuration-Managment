import { describe, expect, it, beforeEach } from 'vitest';
import { useLiveEvents } from './live-events';

describe('live-events store', () => {
  beforeEach(() => {
    useLiveEvents.getState().clear();
  });

  it('appends events in order, newest first', () => {
    useLiveEvents.getState().push({ type: 'backup_completed', payload: { switch_name: 'A' }, ts: '2026-05-20T01:00:00Z' });
    useLiveEvents.getState().push({ type: 'backup_completed', payload: { switch_name: 'B' }, ts: '2026-05-20T01:01:00Z' });
    expect(useLiveEvents.getState().events.map((e) => e.payload.switch_name)).toEqual(['B', 'A']);
  });

  it('caps the buffer at 50 events', () => {
    for (let i = 0; i < 60; i++) {
      useLiveEvents.getState().push({ type: 'x', payload: { i }, ts: new Date().toISOString() });
    }
    expect(useLiveEvents.getState().events.length).toBe(50);
    expect(useLiveEvents.getState().events[0].payload.i).toBe(59);
  });

  it('reports last 24h count', () => {
    const now = Date.now();
    useLiveEvents.getState().push({ type: 'x', payload: {}, ts: new Date(now - 1000).toISOString() });
    useLiveEvents.getState().push({ type: 'x', payload: {}, ts: new Date(now - 25 * 3600 * 1000).toISOString() });
    expect(useLiveEvents.getState().countLast24h()).toBe(1);
  });
});
