import type { ReactNode } from 'react';
import { Redirect } from 'wouter';
import { useAuth } from './AuthProvider';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { accessToken } = useAuth();
  if (!accessToken) return <Redirect to="/login" />;
  return <>{children}</>;
}
