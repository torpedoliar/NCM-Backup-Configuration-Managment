import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BackupProgress } from './BackupProgress';
import type { LiveEvent } from '../api/types';

function event(type: string, switchId: number, name: string, ts: string): LiveEvent {
  return { type, payload: { switch_id: switchId, switch_name: name }, ts };
}

let events: LiveEvent[] = [];

vi.mock('../store/live-events', () => ({
  useLiveEvents: (selector: (s: { events: LiveEvent[] }) => unknown) => selector({ events }),
}));

describe('BackupProgress', () => {
  it('renders the switch name while a backup is running', () => {
    events = [event('backup_started', 2, '10.10.0.50', '2026-08-18T22:55:00+07:00')];
    render(<BackupProgress />);
    expect(screen.getByRole('status').textContent).toContain('10.10.0.50');
  });

  it('hides once the backup completes', () => {
    events = [
      event('backup_completed', 2, '10.10.0.50', '2026-08-18T22:56:00+07:00'),
      event('backup_started', 2, '10.10.0.50', '2026-08-18T22:55:00+07:00'),
    ];
    const { container } = render(<BackupProgress />);
    expect(container.firstChild).toBeNull();
  });

  it('hides when the backup fails', () => {
    events = [event('backup_failed', 2, '10.10.0.50', '2026-08-18T22:56:00+07:00')];
    const { container } = render(<BackupProgress />);
    expect(container.firstChild).toBeNull();
  });

  it('collapses many running backups into a count', () => {
    events = [
      event('backup_started', 1, 'sw-a', '2026-08-18T22:55:00+07:00'),
      event('backup_started', 2, 'sw-b', '2026-08-18T22:55:01+07:00'),
      event('backup_started', 3, 'sw-c', '2026-08-18T22:55:02+07:00'),
      event('backup_started', 4, 'sw-d', '2026-08-18T22:55:03+07:00'),
    ];
    render(<BackupProgress />);
    expect(screen.getByRole('status').textContent).toContain('4 backups');
  });

  it('ignores stale completed event ordering', () => {
    events = [
      event('backup_completed', 2, '10.10.0.50', '2026-08-18T22:56:00+07:00'),
      event('backup_started', 2, '10.10.0.50', '2026-08-18T22:57:00+07:00'),
    ];
    render(<BackupProgress />);
    expect(screen.getByRole('status').textContent).toContain('10.10.0.50');
  });
});