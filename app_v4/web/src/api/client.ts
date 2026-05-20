import axios from 'axios';
import type { CurrentUser, TokenPair } from './types';

export const api = axios.create({ baseURL: '/api/v1' });

export function setAccessToken(token: string | null) {
  if (token) api.defaults.headers.common.Authorization = `Bearer ${token}`;
  else delete api.defaults.headers.common.Authorization;
}

export async function loginRequest(username: string, password: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>('/auth/login', { username, password });
  return data;
}

export async function meRequest(): Promise<CurrentUser> {
  const { data } = await api.get<CurrentUser>('/auth/me');
  return data;
}
