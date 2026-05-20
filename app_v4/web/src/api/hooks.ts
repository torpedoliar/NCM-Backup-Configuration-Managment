import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { BackupRecord, CredentialRecord, JobRecord, SwitchRecord, SystemMetrics, UserRecord } from './types';

const SECOND = 1000;

export function useSystemMetrics() {
  return useQuery({
    queryKey: ['system', 'metrics'],
    queryFn: async () => (await api.get<SystemMetrics>('/system/metrics')).data,
    staleTime: 15 * SECOND,
    refetchInterval: 30 * SECOND,
  });
}

export function useSwitches() {
  return useQuery({
    queryKey: ['switches'],
    queryFn: async () => (await api.get<SwitchRecord[]>('/switches')).data,
    staleTime: 60 * SECOND,
  });
}

export function useCredentials() {
  return useQuery({
    queryKey: ['credentials'],
    queryFn: async () => (await api.get<CredentialRecord[]>('/credentials')).data,
    staleTime: 60 * SECOND,
  });
}

export function useBackups(switchId?: number) {
  return useQuery({
    queryKey: ['backups', switchId],
    queryFn: async () => (await api.get<BackupRecord[]>('/backups', { params: { switch_id: switchId } })).data,
    staleTime: 30 * SECOND,
  });
}

export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: async () => (await api.get<JobRecord[]>('/jobs')).data,
    staleTime: 60 * SECOND,
  });
}

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: async () => (await api.get<UserRecord[]>('/users')).data,
    staleTime: 60 * SECOND,
  });
}

export function useTriggerBackup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (switchId: number) => (await api.post(`/switches/${switchId}/backup`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['backups'] });
      qc.invalidateQueries({ queryKey: ['system', 'metrics'] });
    },
  });
}
