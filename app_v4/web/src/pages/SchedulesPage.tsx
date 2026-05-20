import { DataTable } from '../components/DataTable';
import { useJobs } from '../api/hooks';
import type { JobRecord } from '../api/types';

export function SchedulesPage() {
  const { data = [] } = useJobs();
  return <main><p className="marker">/04 · SCH</p><h1 className="headline">Schedules run without watchers.</h1><DataTable<JobRecord> rows={data} columns={[{ key: 'name', label: 'Name', render: (row) => row.name }, { key: 'interval', label: 'Interval', render: (row) => `${row.interval_minutes}m` }, { key: 'enabled', label: 'State', render: (row) => row.enabled ? 'enabled' : 'disabled' }]} /></main>;
}
