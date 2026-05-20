import { create } from 'zustand';
import type { LiveEvent } from '../api/types';

type LiveActivityState = {
  events: LiveEvent[];
  push: (event: LiveEvent) => void;
};

export const useLiveActivity = create<LiveActivityState>((set) => ({
  events: [],
  push: (event) => set((state) => ({ events: [event, ...state.events].slice(0, 50) })),
}));
