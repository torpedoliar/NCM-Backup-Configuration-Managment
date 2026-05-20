export type Role = 'admin' | 'operator' | 'viewer';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
}

export interface CurrentUser {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
}

export interface SystemMetrics {
  switches: number;
  backups: number;
  jobs: number;
  failures_24h: number;
}

export interface LiveEvent {
  type: string;
  payload: Record<string, unknown>;
  ts: string;
}

export interface SwitchRecord { id: number; name: string; ip: string; host: string; protocol: string; port: number; credential_id: number; credential?: { id: number; name: string }; notes?: string | null; is_active: boolean; }
export interface CredentialRecord { id: number; name: string; username?: string; created_at?: string | null; updated_at?: string | null; }
export interface BackupRecord { id: number; switch_id: number; backup_type: string; success: boolean; file_path?: string | null; created_at: string; message?: string | null; content_hash?: string; size_bytes?: number; }
export interface JobRecord { id: number; switch_id: number; name: string; interval_minutes: number; schedule_hour: number; schedule_minute: number; enabled: boolean; last_run_at?: string | null; }
export interface UserRecord { id: number; username: string; role: Role; is_active: boolean; created_at: string; last_login_at?: string | null; }
export interface ProblemDetails { type: string; title: string; status: number; detail: string; }
