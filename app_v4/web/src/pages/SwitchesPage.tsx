import { DataTable } from '../components/DataTable';
import { useSwitches, useTriggerBackup } from '../api/hooks';
import type { SwitchRecord } from '../api/types';

export function SwitchesPage() {
  const { data = [] } = useSwitches();
  const backup = useTriggerBackup();
  return (
    <main>
      <p className="marker">/02 · INV</p>
      <h1 className="headline">Inventory, sharpened for operators.</h1>
      <DataTable<SwitchRecord> rows={data} columns={[
        { key: 'name', label: 'Name', render: (row) => row.name },
        { key: 'host', label: 'Host', render: (row) => row.ip ?? row.host },
        { key: 'protocol', label: 'Protocol', render: (row) => row.protocol },
        { key: 'action', label: 'Action', render: (row) => <button onClick={() => backup.mutate(row.id)}>Backup now</button> },
      ]} />
    </main>
  );
}
