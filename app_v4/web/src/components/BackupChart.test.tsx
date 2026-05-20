import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BackupChart } from './BackupChart';

vi.mock('../api/hooks', () => ({
  useBackups: () => ({
    data: [
      { id: 1, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-19T10:00:00Z' },
      { id: 2, switch_id: 1, backup_type: 'manual', success: false, created_at: '2026-05-19T10:01:00Z' },
      { id: 3, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-20T10:00:00Z' },
    ],
    isLoading: false,
  }),
}));

describe('BackupChart', () => {
  it('renders a bar per day in the requested range', () => {
    render(<BackupChart range="7d" />);
    const bars = document.querySelectorAll('[data-day-bar]');
    expect(bars.length).toBe(7);
  });
});
