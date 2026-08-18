// Friendly translations for backend / network errors so users see plain
// language instead of raw HTTP/Problem-Details strings.
//
// Order of precedence:
//   1. Network/timeout signals on the Axios error (no `response`).
//   2. HTTP status code → canonical phrase, with override for known sentinel
//      detail strings the backend returns (e.g. "Invalid username or password").
//   3. Fall back to the server-provided `detail`, since validation errors and
//      domain conflicts already produce human-readable detail text.

const FALLBACK = 'Something went wrong. Please try again.';

const STATUS_FALLBACK: Record<number, string> = {
  400: 'The request was rejected. Check the form and try again.',
  401: 'Your session expired. Sign in again to continue.',
  403: "You don't have permission for this action. Ask an admin if you need access.",
  404: 'The item you tried to open is no longer available. It may have been deleted.',
  408: 'The request took too long. The device may be slow or unreachable.',
  409: 'This action conflicts with the current state. Refresh and try again.',
  413: 'The file is too large to upload.',
  415: 'That file type is not supported.',
  422: 'The data was not accepted. Check the highlighted fields.',
  423: 'Account is temporarily locked after too many failed attempts. Wait a few minutes and try again.',
  429: 'Too many requests in a short time. Slow down and try again.',
  500: 'Something broke on the server. Try again; if it keeps failing, check the service logs.',
  502: 'The backend service is unreachable. Check that NCM v4 is running and try again.',
  503: 'A required service is not ready yet. Try again in a moment.',
  504: 'The request timed out waiting for the backend.',
};

const DETAIL_REWRITES: Array<{ match: RegExp; replacement: string }> = [
  {
    match: /^invalid (username or password|credentials)$/i,
    replacement: 'Username or password is wrong. Check your credentials and try again.',
  },
  {
    match: /^invalid bearer token$/i,
    replacement: 'Your session expired. Sign in again to continue.',
  },
  {
    match: /^missing bearer token$/i,
    replacement: 'You need to sign in to continue.',
  },
  {
    match: /^account temporarily locked$/i,
    replacement:
      'Account is temporarily locked after too many failed attempts. Wait a few minutes and try again.',
  },
  {
    match: /^user role is not permitted/i,
    replacement: "You don't have permission for this action. Ask an admin if you need access.",
  },
  {
    match: /^backup service is not initialized$/i,
    replacement: 'Backup service is still starting. Try again in a moment.',
  },
  {
    match: /^cryptoservice is not initialized$/i,
    replacement: 'Encryption service is still starting. Try again in a moment.',
  },
  {
    match: /^retention service is not initialized$/i,
    replacement: 'Retention service is still starting. Try again in a moment.',
  },
  {
    match: /^switch must be deactivated before delete$/i,
    replacement: 'Deactivate the switch first, then delete it.',
  },
  {
    match: /^credential is in use by switches$/i,
    replacement: 'This credential is still used by one or more switches. Update or delete those switches first.',
  },
  {
    match: /^cannot delete yourself$/i,
    replacement: 'You cannot delete the user you are currently signed in as.',
  },
  {
    match: /^one or both backups were not found$/i,
    replacement: 'One or both selected backups no longer exist. Refresh the list and try again.',
  },
  {
    match: /^one or both backup files were not found$/i,
    replacement:
      'Backup file is missing on disk. It may have been deleted manually or by retention.',
  },
  {
    match: /^one or both backup files are not utf-8 text$/i,
    replacement: 'This backup file is not plain text and cannot be diffed.',
  },
  {
    match: /^referenced switch does not exist$/i,
    replacement: 'The selected switch is gone. Reload and pick a current one.',
  },
  {
    match: /^referenced credential does not exist$/i,
    replacement: 'The selected credential is gone. Reload and pick a current one.',
  },
  {
    match: /backend did not start/i,
    replacement: 'Backend did not start in time. Check that the port is free and try again.',
  },
  {
    match: /^auto-?start requires the bundled executable/i,
    replacement: 'Auto-start only works on the installed app, not when running from source.',
  },
  {
    match: /^username already exists$/i,
    replacement: 'That username is already taken. Pick another.',
  },
  {
    match: /^switch name already exists$/i,
    replacement: 'A switch with that name already exists. Pick another name.',
  },
  {
    match: /^credential name already exists$/i,
    replacement: 'A credential with that name already exists. Pick another name.',
  },
  {
    match: /^job not found$/i,
    replacement: 'This schedule no longer exists. Refresh the list.',
  },
  {
    match: /^switch not found$/i,
    replacement: 'This switch no longer exists. Refresh the list.',
  },
  {
    match: /^backup not found$/i,
    replacement: 'This backup record no longer exists. Refresh the list.',
  },
  {
    match: /^credential not found$/i,
    replacement: 'This credential no longer exists. Refresh the list.',
  },
  {
    match: /^user not found$/i,
    replacement: 'This user no longer exists. Refresh the list.',
  },
  {
    match: /^unknown timezone:/i,
    replacement: 'That timezone is not recognized. Pick one from the list.',
  },
  {
    match: /^backup location must be a non-empty path$/i,
    replacement: 'Backup location cannot be empty.',
  },
  {
    match: /timed out|timeout/i,
    replacement: 'The request took too long. The device may be slow or unreachable.',
  },
  {
    match: /connection refused|name (or service )?not known|getaddrinfo|enotfound|econnrefused/i,
    replacement: 'Cannot reach the device. Check IP/host, port, and that the device is online.',
  },
  {
    match: /authentication failed/i,
    replacement: 'The device rejected the credential. Check username, password, and enable secret.',
  },
];

export function humanizeError(error: unknown): string {
  if (error === null || error === undefined) return FALLBACK;
  const err = error as {
    code?: string;
    message?: string;
    response?: { status?: number; data?: unknown };
  };

  const status = err.response?.status;
  const detail = extractDetail(err.response?.data);

  // Network / timeout signals (no response)
  if (!err.response) {
    if (err.code === 'ERR_NETWORK' || /network error/i.test(err.message ?? '')) {
      return 'Cannot reach the backend service. Check that NCM v4 is running and try again.';
    }
    if (err.code === 'ECONNABORTED' || /timeout/i.test(err.message ?? '')) {
      return 'The request took too long. The device may be slow or unreachable.';
    }
  }

  // Sentinel detail rewrites (more user-friendly than the canonical backend message)
  if (detail) {
    for (const rule of DETAIL_REWRITES) {
      if (rule.match.test(detail)) return rule.replacement;
    }
  }

  // Status-code fallback when there is no usable detail
  if (typeof status === 'number') {
    // 5xx: always show the canonical apology — backend internal stack/error
    // strings ("kaboom") are not safe or useful to surface.
    if (status >= 500 && STATUS_FALLBACK[status]) return STATUS_FALLBACK[status];
    if (detail && !looksLikeBoilerplate(detail)) return detail;
    if (STATUS_FALLBACK[status]) return STATUS_FALLBACK[status];
  }

  if (detail) return detail;
  if (typeof err.message === 'string' && err.message) return err.message;
  return FALLBACK;
}

function extractDetail(data: unknown): string | null {
  if (typeof data === 'string') return data || null;
  if (data && typeof data === 'object') {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === 'string' && d.trim()) return d.trim();
  }
  return null;
}

function looksLikeBoilerplate(detail: string): boolean {
  // Generic FastAPI/Starlette error names that don't help users.
  const lower = detail.toLowerCase();
  return (
    lower === 'internal server error' ||
    lower === 'service unavailable' ||
    lower === 'bad gateway' ||
    lower === 'gateway timeout' ||
    lower === 'request validation error'
  );
}
