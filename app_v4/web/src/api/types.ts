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
export interface JobRecord { id: number; switch_id: number; name: string; interval_minutes: number; schedule_hour: number; schedule_minute: number; day_of_week?: string | null; day_of_month?: number | null; enabled: boolean; last_run_at?: string | null; }
export interface UserRecord { id: number; username: string; role: Role; is_active: boolean; created_at: string; last_login_at?: string | null; }
export interface ProblemDetails { type: string; title: string; status: number; detail: string; }

export interface SwitchCreateInput {
  name: string;
  ip: string;
  protocol: string;
  port: number;
  credential_id: number;
  notes?: string | null;
}

export type SwitchUpdateInput = Partial<SwitchCreateInput>;

export interface BackupFilters {
  switch_id?: number;
  success?: boolean;
  backup_type?: 'manual' | 'automatic' | 'manual_schedule';
  from_ts?: string;
  to_ts?: string;
  q?: string;
}

export interface CredentialCreateInput {
  name: string;
  username: string;
  password: string;
  enable_password?: string;
}

export type CredentialUpdateInput = Partial<CredentialCreateInput>;

export interface JobCreateInput {
  switch_id: number;
  name: string;
  interval_minutes: number;
  schedule_hour: number;
  schedule_minute: number;
  day_of_week?: string | null;
  day_of_month?: number | null;
  enabled: boolean;
}

export type JobUpdateInput = Partial<JobCreateInput>;

export interface UserCreateInput {
  username: string;
  password: string;
  role: Role;
  is_active?: boolean;
}

export type UserUpdateInput = Partial<Omit<UserCreateInput, 'password'>>;

export interface AuditEntry {
  id: number;
  user_id: number | null;
  username: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  ip: string | null;
  ts: string;
  detail_json: Record<string, unknown> | null;
}

export interface AuditFilters {
  action?: string;
  user_id?: number;
  from_ts?: string;
  to_ts?: string;
  limit?: number;
  offset?: number;
}

export interface AuditPageData {
  rows: AuditEntry[];
  total: number;
}

export interface SystemStatus {
  service: string;
  version: string;
  started_at: string;
  host: string;
  port: number;
  uptime_seconds: number;
  scheduler_running: boolean;
  db_size_bytes: number;
  data_dir: string;
  backups_dir: string;
  logs_dir: string;
}

export interface RetentionSettings {
  backup_min_keep: number;
  backup_retention_days: number;
  audit_retention_days: number;
  retention_hour: number;
  retention_minute: number;
}

export interface AuthSettings {
  access_token_minutes: number;
  refresh_token_days: number;
  lockout_threshold: number;
  lockout_window_minutes: number;
  lockout_duration_minutes: number;
  password_min_length: number;
  password_require_upper: boolean;
  password_require_lower: boolean;
  password_require_digit: boolean;
  password_require_symbol: boolean;
}

export interface BackupLocationSettings {
  backup_root_folder: string;
  resolved_backups_dir: string;
}

export interface TimeSettings {
  timezone: string;
  ntp_servers: string[];
  ntp_enabled: boolean;
  available_timezones: string[];
  server_now_utc: string;
  server_now_local: string;
}

export interface RetentionRunResult {
  audit_deleted: number;
  backups_deleted: number;
  backup_files_deleted: number;
}

export interface SchedulerJobInfo {
  job_id: number;
  next_run_time: string | null;
  trigger: string | null;
}

export interface SchedulerStatus {
  running: boolean;
  timezone: string;
  lock_acquired: boolean;
  lock_file: string;
  jobs: SchedulerJobInfo[];
}

export interface AutostartStatus {
  installed: boolean;
  ready: boolean;
  raw_status: string | null;
  executable_path: string | null;
}

export interface AutostartUpdate {
  enabled: boolean;
  trigger?: 'startup' | 'logon';
}

export interface LogLine {
  ts: string;
  level: string;
  logger: string;
  message: string;
}

export interface LogsResponse {
  lines: LogLine[];
  total_returned: number;
  log_file: string;
  log_file_size_bytes: number;
}

export interface LogsFilters {
  lines?: number;
  level?: string;
  q?: string;
}

export interface ApiKeyRecord {
  id: number;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked: boolean;
}

export interface ApiKeyCreated {
  id: number;
  name: string;
  prefix: string;
  key: string;
}
