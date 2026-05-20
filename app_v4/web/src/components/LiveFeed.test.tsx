import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LiveFeed } from './LiveFeed';
import { useLiveEvents } from '../store/live-events';

describe('LiveFeed', () => {
  beforeEach(() => useLiveEvents.getState().clear());

  it('renders events from the live store newest first', () => {
    useLiveEvents.getState().push({
      type: 'backup_completed',
      payload: { switch_name: 'SW-CORE-01', backup_id: 1 },
      ts: '2026-05-20T01:00:00Z',
    });
    useLiveEvents.getState().push({
      type: 'backup_failed',
      payload: { switch_name: 'SW-EDGE-07', message: 'timeout' },
      ts: '2026-05-20T01:01:00Z',
    });

    render(<LiveFeed />);

    const items = screen.getAllByRole('listitem');
    expect(items[0].textContent).toContain('SW-EDGE-07');
    expect(items[1].textContent).toContain('SW-CORE-01');
  });

  it('shows an empty state when there are no events', () => {
    render(<LiveFeed />);
    expect(screen.getByText(/no recent activity/i)).toBeInTheDocument();
  });
});
