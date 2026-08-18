import { useEffect, useState } from 'react';
import { StatusPill } from '../components/StatusPill';
import { BackupProgress } from '../components/BackupProgress';
import { useTimeSettings } from '../api/hooks';
import { rememberTimezone } from '../lib/fmt';

function formatTimezoneOffset(tz: string, now: Date): string {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'shortOffset' });
    const parts = formatter.formatToParts(now);
    const offset = parts.find((p) => p.type === 'timeZoneName')?.value ?? '';
    return offset.replace('GMT', 'UTC') || 'UTC';
  } catch {
    return 'UTC';
  }
}

function formatLocalTime(tz: string, now: Date): string {
  try {
    const fmt = new Intl.DateTimeFormat('sv-SE', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
    return fmt.format(now).replace('T', ' ');
  } catch {
    return now.toISOString().replace('T', ' ').slice(0, 19);
  }
}

export function Topbar() {
  const { data: timeSettings } = useTimeSettings();
  const tz = timeSettings?.timezone ?? 'Asia/Jakarta';
  useEffect(() => {
    rememberTimezone(tz);
  }, [tz]);
  const [now, setNow] = useState<Date>(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const offset = formatTimezoneOffset(tz, now);
  const localTime = formatLocalTime(tz, now);

  return (
    <header className="ops-topbar">
      <div className="breadcrumb">
        <span>MONITORING</span>
        <b>/</b>
        <strong>/ Dashboard</strong>
      </div>
      <div className="topbar-right">
        <BackupProgress />
        <StatusPill tone="green">SERVICE / RUNNING</StatusPill>
        <span className="marker" title={tz}>{offset}</span>
        <span className="topbar-time number">{localTime}</span>
      </div>
    </header>
  );
}
