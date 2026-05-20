const fallbackEvents = [
  ['22:00:22', 'ok', 'SW-EDGE-07 backup completed', '4.1s'],
  ['22:00:18', 'fail', 'SW-EDGE-07 timeout retry 1/3', ''],
  ['22:00:14', 'ok', 'SW-EDGE-03 backup completed', '1.8s'],
  ['22:00:12', 'ok', 'SW-CORE-01 backup completed', '2.3s'],
  ['21:55:08', 'info', 'Scheduled job triggered', 'daily-22h'],
  ['21:42:31', 'auth', 'admin session opened', 'from 10.0.5.42'],
  ['21:38:09', 'warn', 'SW-CORE-02 config diff detected', '+12 -3'],
  ['21:30:00', 'info', 'Retention sweep', 'purged 4 files'],
] as const;

function toneClass(tone: string): string {
  if (tone === 'fail') return 'status-red';
  if (tone === 'auth') return 'status-violet';
  if (tone === 'warn') return 'status-amber';
  return 'status-green';
}

function toneSymbol(tone: string): string {
  if (tone === 'fail') return '×';
  if (tone === 'warn') return '!';
  if (tone === 'auth') return '◆';
  return '✓';
}

export function LiveFeed() {
  return (
    <div className="live-feed">
      <div className="live-header">
        <span className="live-dot" /> LIVE
      </div>
      {fallbackEvents.map(([time, tone, message, meta]) => (
        <div className="live-row" key={`${time}-${message}`}>
          <span className="live-time number">{time}</span>
          <span className={`live-icon ${toneClass(tone)}`}>{toneSymbol(tone)}</span>
          <strong>{message}</strong>
          <span>{meta}</span>
        </div>
      ))}
      <div className="live-footer">
        <span><b>108</b> EVENTS / 24H</span>
        <span>VIEW ALL ↗</span>
      </div>
    </div>
  );
}
