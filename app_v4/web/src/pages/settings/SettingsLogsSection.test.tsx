import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsLogsSection } from './SettingsLogsSection';

const useLogsMock = vi.fn();
const refetch = vi.fn();

vi.mock('../../api/hooks', () => ({
  useLogs: (filters: unknown, autoRefresh: boolean) => {
    useLogsMock(filters, autoRefresh);
    return {
      data: {
        lines: [
          { ts: '2026-05-20 09:00:00', level: 'INFO',    logger: 'uvicorn', message: 'started' },
          { ts: '2026-05-20 09:00:01', level: 'WARNING', logger: 'uvicorn', message: 'slow disk' },
          { ts: '2026-05-20 09:00:02', level: 'ERROR',   logger: 'uvicorn', message: 'failed conn' },
        ],
        total_returned: 3,
        log_file: '/tmp/ncm-v4.log',
        log_file_size_bytes: 12345,
      },
      refetch,
    };
  },
}));

describe('SettingsLogsSection', () => {
  it('renders lines with level color classes', () => {
    render(<SettingsLogsSection />);
    expect(document.querySelector('.level-INFO')).not.toBeNull();
    expect(document.querySelector('.level-WARNING')).not.toBeNull();
    expect(document.querySelector('.level-ERROR')).not.toBeNull();
  });

  it('changing level dropdown refetches with level param', async () => {
    const user = userEvent.setup();
    useLogsMock.mockClear();
    render(<SettingsLogsSection />);
    await user.selectOptions(screen.getByLabelText(/level/i), 'ERROR');
    await waitFor(() => {
      const calls = useLogsMock.mock.calls;
      const lastFilters = calls[calls.length - 1]![0] as { level?: string };
      expect(lastFilters.level).toBe('ERROR');
    });
  });

  it('Refresh button calls refetch', async () => {
    const user = userEvent.setup();
    refetch.mockClear();
    render(<SettingsLogsSection />);
    await user.click(screen.getByRole('button', { name: /refresh/i }));
    expect(refetch).toHaveBeenCalled();
  });
});
