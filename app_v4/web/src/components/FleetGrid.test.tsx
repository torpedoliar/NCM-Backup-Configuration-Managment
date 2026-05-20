import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FleetGrid } from './FleetGrid';

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({
    data: [
      { id: 1, name: 'SW-CORE-01', ip: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
      { id: 2, name: 'SW-EDGE-07', ip: '10.0.0.2', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
    ],
    isLoading: false,
  }),
  useLatestBackupPerSwitch: () => ({
    data: [
      { id: 5, switch_id: 1, backup_type: 'manual', success: true, created_at: new Date().toISOString() },
      { id: 6, switch_id: 2, backup_type: 'manual', success: false, created_at: new Date(Date.now() - 3600 * 1000).toISOString(), message: 'timeout' },
    ],
    isLoading: false,
  }),
}));

describe('FleetGrid', () => {
  it('renders one cell per switch with status derived from last backup', () => {
    render(<FleetGrid />);
    const cells = screen.getAllByRole('listitem');
    expect(cells).toHaveLength(2);
    expect(cells[0]).toHaveAttribute('data-state', 'ok');
    expect(cells[1]).toHaveAttribute('data-state', 'fail');
  });
});
