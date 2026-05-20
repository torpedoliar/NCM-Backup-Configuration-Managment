import { OpsPanel } from './OpsPanel';

type KpiCellProps = {
  marker: string;
  label: string;
  value: string;
  suffix?: string;
  delta?: string;
  tone?: 'green' | 'amber' | 'red';
  footer?: string;
  progress?: number;
};

export function KpiCell({ marker, label, value, suffix, delta, tone = 'amber', footer, progress }: KpiCellProps) {
  return (
    <OpsPanel marker={marker} className="kpi-cell">
      <div className="kpi-label">▪ {label}</div>
      <div className="kpi-main number">
        <span>{value}</span>
        {suffix ? <small>{suffix}</small> : null}
      </div>
      {typeof progress === 'number' ? (
        <div className="kpi-progress">
          <span style={{ width: `${progress}%` }} />
        </div>
      ) : null}
      {delta ? <div className={`kpi-delta status-${tone}`}>{delta}</div> : null}
      {footer ? <div className="kpi-footer marker">// {footer}</div> : null}
    </OpsPanel>
  );
}
