import { create } from 'zustand';
import type { LiveEvent } from '../api/types';

const MAX_EVENTS = 50;

interface LiveEventsState {
  events: LiveEvent[];
  push: (event: LiveEvent) => void;
  clear: () => void;
  countLast24h: () => number;
}

export const useLiveEvents = create<LiveEventsState>((set, get) => ({
  events: [],
  push: (event) =>
    set((state) => ({
      events: [event, ...state.events].slice(0, MAX_EVENTS),
    })),
  clear: () => set({ events: [] }),
  countLast24h: () => {
    const cutoff = Date.now() - 24 * 60 * 60 * 1000;
    return get().events.filter((e) => Date.parse(e.ts) >= cutoff).length;
  },
}));
