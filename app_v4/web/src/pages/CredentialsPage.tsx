import { DataTable } from '../components/DataTable';
import { useCredentials } from '../api/hooks';
import type { CredentialRecord } from '../api/types';

export function CredentialsPage() {
  const { data = [] } = useCredentials();
  return <main><p className="marker">/03 · CREDS</p><h1 className="headline">Credentials stay write-only.</h1><DataTable<CredentialRecord> rows={data} columns={[{ key: 'name', label: 'Name', render: (row) => row.name }, { key: 'secret', label: 'Secret', render: () => '••••••••' }]} /></main>;
}
