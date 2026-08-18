import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DecodePage } from './DecodePage';

const DECODED = {
  backup_id: 42,
  switch_id: 1,
  switch_name: 'WS Lab',
  protocol: 'websmart-snmp',
  dialect: 'websmart',
  hostname: 'ICT Network SW',
  backup_taken_at: '2026-08-18T04:00:00Z',
  vlans: [
    { id: 88, name: 'IPH-DEVICE' },
    { id: 23, name: null },
  ],
  ports: [
    { name: '1', description: 'uplink', enabled: true, mode: 'trunk', native_vlan: 11, access_vlan: null, trunk_allowed_vlans: [88] },
    { name: '2', description: null, enabled: false, mode: 'access', native_vlan: null, access_vlan: 23, trunk_allowed_vlans: [] },
  ],
  parse_warnings: [] as string[],
};

const state = {
  backups: [{ id: 42, switch_id: 1, created_at: '2026-08-18T04:00:00Z', success: true }],
  decoded: DECODED,
};

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [{ id: 1, name: 'WS Lab' }] }),
  useFilteredBackups: () => ({ data: state.backups }),
  useDecodedBackup: () => ({ data: state.decoded, isFetching: false, error: null }),
}));

describe('DecodePage', () => {
  it('renders decoded hostname, VLANs and ports', () => {
    render(<DecodePage />);
    expect(screen.getByText('ICT Network SW')).toBeTruthy();
    expect(screen.getByText('88 · IPH-DEVICE')).toBeTruthy();
    expect(screen.getAllByText('23').length).toBeGreaterThan(0);
    expect(screen.getByText('trunk')).toBeTruthy();
    expect(screen.getByText('SHUT')).toBeTruthy();
    expect(screen.getByText('88')).toBeTruthy();
  });

  it('shows parse warnings as an alert', () => {
    state.decoded = { ...DECODED, parse_warnings: ['unknown switch config dialect; nothing parsed'] };
    render(<DecodePage />);
    expect(screen.getByRole('alert').textContent).toContain('unknown switch config dialect');
  });

  it('shows empty state when the switch has no backups', () => {
    state.backups = [];
    render(<DecodePage />);
    expect(screen.getByText('No backups for this switch.')).toBeTruthy();
  });
});
