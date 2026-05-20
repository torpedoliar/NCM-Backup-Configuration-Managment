import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CredentialCombo } from './CredentialCombo';

const credentials = [
  { id: 1, name: 'Lab admin' },
  { id: 2, name: 'Datacenter ops' },
];

describe('CredentialCombo', () => {
  it('selects an existing credential', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<CredentialCombo credentials={credentials} value={null} onChange={onChange} onCreateNew={vi.fn()} />);
    await user.selectOptions(screen.getByRole('combobox'), '1');
    expect(onChange).toHaveBeenCalledWith(1);
  });

  it('triggers onCreateNew when "+ New credential" picked', async () => {
    const user = userEvent.setup();
    const onCreateNew = vi.fn();
    render(<CredentialCombo credentials={credentials} value={null} onChange={vi.fn()} onCreateNew={onCreateNew} />);
    await user.selectOptions(screen.getByRole('combobox'), screen.getByRole('option', { name: /\+ new credential/i }));
    expect(onCreateNew).toHaveBeenCalled();
  });
});
