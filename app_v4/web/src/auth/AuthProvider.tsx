import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useLocation } from 'wouter';
import { api, attachAuthInterceptor, loginRequest, meRequest, setAccessToken, setRefreshListener, setRefreshToken } from '../api/client';
import type { CurrentUser } from '../api/types';

type AuthValue = {
  accessToken: string | null;
  refreshToken: string | null;
  user: CurrentUser | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthValue | null>(null);

type AuthProviderProps = {
  children: ReactNode;
  initialAccessToken?: string | null;
  initialRefreshToken?: string | null;
};

export function AuthProvider({ children, initialAccessToken, initialRefreshToken }: AuthProviderProps) {
  const [, navigate] = useLocation();
  const [accessToken, setToken] = useState<string | null>(
    () => initialAccessToken ?? localStorage.getItem('access_token'),
  );
  const [refreshToken, setRefreshTokenState] = useState<string | null>(
    () => initialRefreshToken ?? localStorage.getItem('refresh_token'),
  );
  const [user, setUser] = useState<CurrentUser | null>(null);
  const loggingOutRef = useRef(false);

  useEffect(() => {
    setAccessToken(accessToken);
    setRefreshToken(refreshToken);
    // Keep the axios layer in sync whenever a silent refresh rotates the pair.
    const listener = (newAccess: string, newRefresh: string) => {
      setToken(newAccess);
      setRefreshTokenState(newRefresh);
    };
    setRefreshListener(listener);
    return () => setRefreshListener(null);
  }, [accessToken, refreshToken]);

  useEffect(() => {
    if (!accessToken) {
      setUser(null);
      return;
    }
    let cancelled = false;
    meRequest()
      .then((u) => { if (!cancelled) setUser(u); })
      .catch(() => { /* 401 handled by attachAuthInterceptor; other errors leave user null */ });
    return () => { cancelled = true; };
  }, [accessToken]);

  const logout = useCallback(async () => {
    if (loggingOutRef.current) return;
    loggingOutRef.current = true;
    const rt = refreshToken;
    if (rt) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);
      try {
        await api.post('/auth/logout', { refresh_token: rt }, { signal: controller.signal });
      } catch {
        // Ignore failures (network, 4xx, abort) — logout proceeds locally regardless.
      } finally {
        clearTimeout(timeoutId);
      }
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setAccessToken(null);
    setRefreshToken(null);
    setToken(null);
    setRefreshTokenState(null);
    setUser(null);
    navigate('/login');
    loggingOutRef.current = false;
  }, [navigate, refreshToken]);

  useEffect(() => {
    return attachAuthInterceptor(() => {
      if (localStorage.getItem('access_token')) {
        void logout();
      }
    });
  }, [logout]);

  const value = useMemo<AuthValue>(() => ({
    accessToken,
    refreshToken,
    user,
    async login(username, password) {
      const tokenPair = await loginRequest(username, password);
      localStorage.setItem('access_token', tokenPair.access_token);
      localStorage.setItem('refresh_token', tokenPair.refresh_token);
      setAccessToken(tokenPair.access_token);
      setRefreshToken(tokenPair.refresh_token);
      setToken(tokenPair.access_token);
      setRefreshTokenState(tokenPair.refresh_token);
      navigate('/');
    },
    logout,
  }), [accessToken, refreshToken, user, navigate, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('AuthContext missing');
  return context;
}

export function useOptionalAuth(): AuthValue | null {
  return useContext(AuthContext);
}
