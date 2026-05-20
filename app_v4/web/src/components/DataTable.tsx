import type { ReactNode } from 'react';

export function DataTable<T>({ rows, columns }: { rows: T[]; columns: { key: string; label: string; render: (row: T) => ReactNode }[] }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid var(--line)' }}>
      <thead><tr>{columns.map((column) => <th className="marker" style={{ textAlign: 'left', padding: 12 }} key={column.key}>{column.label}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column) => <td style={{ borderTop: '1px dashed var(--line-2)', padding: 12 }} key={column.key}>{column.render(row)}</td>)}</tr>)}</tbody>
    </table>
  );
}
