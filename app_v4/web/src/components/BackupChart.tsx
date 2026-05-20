const days = [18, 22, 24, 20, 26, 29, 27, 24, 28, 31, 27, 32, 30, 29];
const failed = [1, 0, 0, 2, 0, 0, 0, 1, 0, 0, 0, 0, 2, 1];

export function BackupChart() {
  const max = Math.max(...days);
  return (
    <div className="bar-chart" aria-label="backup activity chart">
      <div className="chart-legend marker">
        <span className="legend-success" /> SUCCESS
        <span className="legend-failed" /> FAILED
        <span className="legend-avg" /> AVG
      </div>
      <div className="chart-bars">
        {days.map((value, index) => (
          <div className="chart-day" key={index}>
            <div className="bar-stack" style={{ height: `${(value / max) * 210}px` }}>
              <span className="bar-failed" style={{ height: `${failed[index] * 6}px` }} />
            </div>
            <span className="chart-label">05-{String(index + 5).padStart(2, '0')}</span>
            {index === days.length - 1 ? <strong>TODAY</strong> : null}
          </div>
        ))}
      </div>
      <div className="avg-line"><span>AVG 24.1</span></div>
    </div>
  );
}
