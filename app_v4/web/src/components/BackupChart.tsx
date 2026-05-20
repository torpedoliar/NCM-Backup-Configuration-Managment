import { Line, LineChart, ResponsiveContainer, XAxis, YAxis } from 'recharts';

const data = Array.from({ length: 14 }, (_, index) => ({ day: index + 1, backups: index + 3 }));

export function BackupChart() {
  return <ResponsiveContainer width="100%" height={180}><LineChart data={data}><XAxis dataKey="day" stroke="var(--muted)" /><YAxis stroke="var(--muted)" /><Line type="monotone" dataKey="backups" stroke="var(--amber)" dot={false} /></LineChart></ResponsiveContainer>;
}
