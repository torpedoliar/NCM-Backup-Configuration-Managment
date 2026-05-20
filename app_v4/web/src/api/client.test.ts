import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, attachAuthInterceptor } from './client';

describe('axios 401 interceptor', () => {
  let mock: MockAdapter;
  let onUnauthorized: ReturnType<typeof vi.fn>;
  let detach: () => void;

  beforeEach(() => {
    mock = new MockAdapter(api);
    onUnauthorized = vi.fn();
    detach = attachAuthInterceptor(onUnauthorized);
  });

  afterEach(() => {
    mock.restore();
    detach();
  });

  it('invokes onUnauthorized when server returns 401', async () => {
    mock.onGet('/auth/me').reply(401, { detail: 'Invalid bearer token' });

    await expect(api.get('/auth/me')).rejects.toMatchObject({ response: { status: 401 } });

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not invoke onUnauthorized for non-401 errors', async () => {
    mock.onGet('/switches').reply(500, { detail: 'Server error' });

    await expect(api.get('/switches')).rejects.toMatchObject({ response: { status: 500 } });

    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
