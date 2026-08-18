export function number(value: number | undefined): string {
  return (value ?? 0).toLocaleString();
}

const STORAGE_KEY = 'ncm.timezone';
const FALLBACK_TZ = 'Asia/Jakarta';

export function rememberTimezone(tz: string | undefined | null): void {
  if (typeof window === 'undefined') return;
  if (tz) {
    try {
      window.localStorage.setItem(STORAGE_KEY, tz);
    } catch {
      // localStorage may be unavailable; render-time fallback handles it.
    }
  }
}

export function effectiveTimezone(): string {
  if (typeof window === 'undefined') return FALLBACK_TZ;
  try {
    return window.localStorage.getItem(STORAGE_KEY) || FALLBACK_TZ;
  } catch {
    return FALLBACK_TZ;
  }
}

const DATE_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
};

const TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
};

export function formatTzDateTime(value: string | number | Date | null | undefined, tz?: string): string {
  if (value === null || value === undefined || value === '') return '—';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const zone = tz || effectiveTimezone();
  try {
    return new Intl.DateTimeFormat('sv-SE', { timeZone: zone, ...DATE_TIME_OPTIONS })
      .format(date)
      .replace('T', ' ');
  } catch {
    return date.toLocaleString();
  }
}

export function formatTzTime(value: string | number | Date | null | undefined, tz?: string): string {
  if (value === null || value === undefined || value === '') return '—';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const zone = tz || effectiveTimezone();
  try {
    return new Intl.DateTimeFormat('sv-SE', { timeZone: zone, ...TIME_OPTIONS }).format(date);
  } catch {
    return date.toLocaleTimeString();
  }
}
