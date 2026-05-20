import { DataTable } from '../components/DataTable';
import { useUsers } from '../api/hooks';
import type { UserRecord } from '../api/types';

export function UsersPage() {
  const { data = [] } = useUsers();
  return <main><p className="marker">/07 · USERS</p><h1 className="headline">Access is operational control.</h1><DataTable<UserRecord> rows={data} columns={[{ key: 'username', label: 'Username', render: (row) => row.username }, { key: 'role', label: 'Role', render: (row) => row.role }, { key: 'active', label: 'Active', render: (row) => row.is_active ? 'yes' : 'no' }]} /></main>;
}
