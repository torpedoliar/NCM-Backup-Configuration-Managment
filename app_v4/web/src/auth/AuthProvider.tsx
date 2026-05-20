import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useLocation } from 'wouter';
import { attachAuthInterceptor, loginRequest, setAccessToken } from '../api/client';
import type { CurrentUser } from '../api/types';

type AuthValue = {
  accessToken: string | null;
  user: CurrentUser | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

export const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [, navigate] = useLocation();
  const [accessToken, setToken] = useState<string | null>(() => localStorage.getItem('access_token'));
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    setAccessToken(accessToken);
  }, [accessToken]);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setAccessToken(null);
    setToken(null);
    setUser(null);
    navigate('/login');
  }, [navigate]);

  useEffect(() => {
    return attachAuthInterceptor(() => {
      if (localStorage.getItem('access_token')) {
        logout();
      }
    });
  }, [logout]);

  const value = useMemo<AuthValue>(() => ({
    accessToken,
    user,
    async login(username, password) {
      const tokenPair = await loginRequest(username, password);
      localStorage.setItem('access_token', tokenPair.access_token);
      localStorage.setItem('refresh_token', tokenPair.refresh_token);
      setAccessToken(tokenPair.access_token);
      setToken(tokenPair.access_token);
      navigate('/');
    },
    logout,
  }), [accessToken, user, navigate, logout]);

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
