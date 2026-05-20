import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  BackupRecord,
  CredentialCreateInput,
  CredentialRecord,
  CredentialUpdateInput,
  JobRecord,
  SwitchCreateInput,
  SwitchRecord,
  SwitchUpdateInput,
  SystemMetrics,
  UserRecord,
} from './types';

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

export function useLatestBackupPerSwitch() {
  return useQuery({
    queryKey: ['backups', 'latest-per-switch'],
    queryFn: async () => (await api.get<BackupRecord[]>('/backups', { params: { limit: 1000 } })).data,
    staleTime: 30 * SECOND,
  });
}

export function useCreateSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: SwitchCreateInput) => (await api.post<SwitchRecord>('/switches', input)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['switches'] });
      qc.invalidateQueries({ queryKey: ['system', 'metrics'] });
    },
  });
}

export function useUpdateSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: number; input: SwitchUpdateInput }) =>
      (await api.patch<SwitchRecord>(`/switches/${vars.id}`, vars.input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['switches'] }),
  });
}

export function useDeactivateSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.post(`/switches/${id}/deactivate`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['switches'] }),
  });
}

export function useActivateSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.post(`/switches/${id}/activate`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['switches'] }),
  });
}

export function useDeleteSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/switches/${id}`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['switches'] });
      qc.invalidateQueries({ queryKey: ['system', 'metrics'] });
    },
  });
}

export function useCreateCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: CredentialCreateInput) =>
      (await api.post<CredentialRecord>('/credentials', input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
}

export function useUpdateCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: number; input: CredentialUpdateInput }) =>
      (await api.patch<CredentialRecord>(`/credentials/${vars.id}`, vars.input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
}

export function useDeleteCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/credentials/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
}
