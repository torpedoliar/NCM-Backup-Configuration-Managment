import { useEffect, useState } from 'react';
import { StatusPill } from '../components/StatusPill';

function nowTimecode(): string {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

export function Topbar() {
  const [tick, setTick] = useState(nowTimecode());
  useEffect(() => {
    const id = setInterval(() => setTick(nowTimecode()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="ops-topbar">
      <div className="breadcrumb">
        <span>MONITORING</span>
        <b>/</b>
        <strong>/ Dashboard</strong>
      </div>
      <div className="topbar-right">
        <StatusPill tone="green">SERVICE / RUNNING</StatusPill>
        <span className="marker">UTC+07</span>
        <span className="topbar-time number">{tick}</span>
      </div>
    </header>
  );
}
