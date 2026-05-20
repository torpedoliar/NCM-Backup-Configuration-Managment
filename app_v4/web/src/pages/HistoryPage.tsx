import { DataTable } from '../components/DataTable';
import { useBackups } from '../api/hooks';
import type { BackupRecord } from '../api/types';

export function HistoryPage() {
  const { data = [] } = useBackups();
  return <main><p className="marker">/05 · HIST</p><h1 className="headline">Every config has a trail.</h1><DataTable<BackupRecord> rows={data} columns={[{ key: 'id', label: 'ID', render: (row) => row.id }, { key: 'type', label: 'Type', render: (row) => row.backup_type }, { key: 'state', label: 'State', render: (row) => row.success ? 'success' : 'failed' }]} /></main>;
}
