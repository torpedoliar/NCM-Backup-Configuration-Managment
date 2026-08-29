import axios from 'axios';
import type { AxiosRequestConfig } from 'axios';
import type { CurrentUser, TokenPair } from './types';

export const api = axios.create({ baseURL: '/api/v1' });

let accessTokenStore: string | null = null;
let refreshTokenStore: string | null = null;
let onTokensRefreshed: ((accessToken: string, refreshToken: string) => void) | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null) {
  accessTokenStore = token;
  if (token) api.defaults.headers.common.Authorization = `Bearer ${token}`;
  else delete api.defaults.headers.common.Authorization;
}

export function setRefreshToken(token: string | null) {
  refreshTokenStore = token;
}

/** Register a listener called whenever the access/refresh pair is rotated. */
export function setRefreshListener(
  listener: ((accessToken: string, refreshToken: string) => void) | null,
) {
  onTokensRefreshed = listener;
}

/**
 * Rotate the access token once, single-flight across concurrent 401s.
 * Returns the new access token on success, or null when no refresh token is
 * present or the server rejects it (expired session → caller should log out).
 */
export function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = performRefresh().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

async function performRefresh(): Promise<string | null> {
  const token = refreshTokenStore;
  if (!token) return null;
  try {
    const { data } = await api.post<TokenPair>('/auth/refresh', {
      refresh_token: token,
    });
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    setAccessToken(data.access_token);
    refreshTokenStore = data.refresh_token;
    onTokensRefreshed?.(data.access_token, data.refresh_token);
    return accessTokenStore;
  } catch {
    return null;
  }
}

// Requests already replayed after a refresh, to avoid infinite retry loops.
const retried = new WeakSet<AxiosRequestConfig>();

export function attachAuthInterceptor(onUnauthorized: () => void): () => void {
  const id = api.interceptors.response.use(
    (response) => response,
    async (error) => {
      const status = error?.response?.status;
      const url = typeof error?.config?.url === 'string' ? error.config.url : '';
      // Never auto-refresh the credential-bound auth endpoints themselves;
      // a 401 there is final. /auth/me is fine to refresh (bootstrap case).
      const nonRefreshable = ['/auth/login', '/auth/logout', '/auth/refresh'];
      if (status === 401 && !nonRefreshable.some((p) => url.startsWith(p))) {
        const config = error.config as AxiosRequestConfig | undefined;
        if (config && !retried.has(config)) {
          retried.add(config);
          const newToken = await refreshAccessToken();
          if (newToken) {
            config.headers = { ...(config.headers ?? {}), Authorization: `Bearer ${newToken}` };
            return api.request(config);
          }
        }
      }
      if (status === 401) {
        onUnauthorized();
      }
      return Promise.reject(error);
    },
  );
  return () => api.interceptors.response.eject(id);
}

export async function loginRequest(username: string, password: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>('/auth/login', { username, password });
  return data;
}

export async function meRequest(): Promise<CurrentUser> {
  const { data } = await api.get<CurrentUser>('/auth/me');
  return data;
}
