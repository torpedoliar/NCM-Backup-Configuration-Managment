import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  AuditEntry,
  AuditFilters,
  AuditPageData,
  BackupFilters,
  BackupRecord,
  CredentialCreateInput,
  CredentialRecord,
  CredentialUpdateInput,
  JobCreateInput,
  JobRecord,
  JobUpdateInput,
  SwitchCreateInput,
  SwitchRecord,
  SwitchUpdateInput,
  SystemMetrics,
  UserCreateInput,
  UserRecord,
  UserUpdateInput,
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

export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: JobCreateInput) => (await api.post<JobRecord>('/jobs', input)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      qc.invalidateQueries({ queryKey: ['system', 'metrics'] });
    },
  });
}

export function useUpdateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: number; input: JobUpdateInput }) =>
      (await api.patch<JobRecord>(`/jobs/${vars.id}`, vars.input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/jobs/${id}`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      qc.invalidateQueries({ queryKey: ['system', 'metrics'] });
    },
  });
}

export function useRunJobNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.post(`/jobs/${id}/run`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['backups'] });
      qc.invalidateQueries({ queryKey: ['system', 'metrics'] });
    },
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: UserCreateInput) => (await api.post<UserRecord>('/users', input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: number; input: UserUpdateInput }) =>
      (await api.patch<UserRecord>(`/users/${vars.id}`, vars.input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/users/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useResetUserPassword() {
  return useMutation({
    mutationFn: async (vars: { id: number; password: string }) =>
      (await api.post(`/users/${vars.id}/password`, { password: vars.password })).data,
  });
}

export function useFilteredBackups(filters: BackupFilters) {
  return useQuery({
    queryKey: ['backups', 'filtered', filters],
    queryFn: async () => (await api.get<BackupRecord[]>('/backups', { params: filters })).data,
    staleTime: 15 * SECOND,
  });
}

export async function fetchBackupContent(id: number): Promise<string> {
  return (await api.get<string>(`/backups/${id}/content`, { responseType: 'text' })).data as unknown as string;
}

export function useDeleteBackup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/backups/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backups'] }),
  });
}

export async function downloadBackup(id: number): Promise<void> {
  const response = await api.get(`/backups/${id}/content`, {
    params: { download: true },
    responseType: 'blob',
  });
  const blob = response.data as Blob;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const cd = response.headers['content-disposition'] as string | undefined;
  const match = cd?.match(/filename="?([^"]+)"?/);
  a.download = match?.[1] ?? `backup-${id}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

export function useAudit(filters: AuditFilters) {
  return useQuery<AuditPageData>({
    queryKey: ['audit', filters],
    queryFn: async () => {
      const response = await api.get<AuditEntry[]>('/audit', { params: filters });
      const headerTotal = response.headers['x-total-count'];
      const total = Number(headerTotal ?? response.data.length);
      return { rows: response.data, total: Number.isFinite(total) ? total : response.data.length };
    },
    staleTime: 30 * SECOND,
  });
}
