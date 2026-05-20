const fleet = [
  ['SW-CORE-01', 'ok', '2m'], ['SW-CORE-02', 'ok', '3m'], ['SW-EDGE-01', 'ok', '5m'], ['SW-EDGE-02', 'ok', '5m'],
  ['SW-EDGE-03', 'ok', '2m'], ['SW-EDGE-04', 'ok', '7m'], ['SW-EDGE-05', 'ok', '4m'], ['SW-EDGE-06', 'ok', '6m'],
  ['SW-EDGE-07', 'fail', '1h'], ['SW-EDGE-08', 'warn', '15m'], ['SW-DIST-01', 'ok', '3m'], ['SW-DIST-02', 'ok', '4m'],
] as const;

export function FleetGrid() {
  return (
    <div className="fleet-grid-wrap">
      <div className="fleet-legend marker">
        <span><span className="dot ok" />OK · 10</span>
        <span><span className="dot warn" />WARN · 1</span>
        <span><span className="dot fail" />FAIL · 1</span>
      </div>
      <div className="fleet-grid">
        {fleet.map(([name, state, age]) => (
          <div className={`fleet-tile fleet-${state}`} key={name}>
            <strong>{name}</strong>
            <span className={`dot ${state}`} />
            <small>{age}</small>
          </div>
        ))}
      </div>
    </div>
  );
}
