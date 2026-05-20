import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AuditFilters } from '../api/types';
import { AuditPage } from './AuditPage';

const useAuditMock = vi.fn((_filters: AuditFilters) => ({
  data: {
    rows: [
      {
        id: 1,
        user_id: 1,
        action: 'auth.login_success',
        target_type: null,
        target_id: null,
        ip: '127.0.0.1',
        ts: '2026-05-20T01:00:00Z',
        detail_json: { client: 'desktop' },
      },
      {
        id: 2,
        user_id: 1,
        action: 'switch.created',
        target_type: 'switch',
        target_id: '5',
        ip: '127.0.0.1',
        ts: '2026-05-20T01:01:00Z',
        detail_json: null,
      },
    ],
    total: 100,
  },
  isLoading: false,
}));

vi.mock('../api/hooks', () => ({
  useAudit: (filters: AuditFilters) => useAuditMock(filters),
}));

describe('AuditPage', () => {
  it('renders rows from useAudit', () => {
    render(<AuditPage />);
    expect(screen.getByText('auth.login_success')).toBeInTheDocument();
    expect(screen.getByText('switch.created')).toBeInTheDocument();
  });

  it('changing action group dropdown updates filter prefix', async () => {
    const user = userEvent.setup();
    useAuditMock.mockClear();
    render(<AuditPage />);
    await user.selectOptions(screen.getByLabelText(/action/i), 'auth.');
    const calls = useAuditMock.mock.calls;
    const lastCall = calls[calls.length - 1];
    const lastFilters = (lastCall ? lastCall[0] : {}) as AuditFilters;
    expect(lastFilters.action).toBe('auth.');
  });

  it('Load more increases the limit', async () => {
    const user = userEvent.setup();
    useAuditMock.mockClear();
    render(<AuditPage />);
    await user.click(screen.getByRole('button', { name: /load .* more/i }));
    const calls = useAuditMock.mock.calls;
    const lastCall = calls[calls.length - 1];
    const lastFilters = (lastCall ? lastCall[0] : {}) as AuditFilters;
    expect(lastFilters.limit ?? 0).toBeGreaterThan(50);
  });

  it('toggles detail JSON panel', async () => {
    const user = userEvent.setup();
    render(<AuditPage />);
    await user.click(screen.getByRole('button', { name: /view json/i }));
    expect(screen.getByText(/"client": "desktop"/)).toBeInTheDocument();
  });
});
