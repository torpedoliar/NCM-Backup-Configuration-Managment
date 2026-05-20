export function KpiCell({ marker, label, value }: { marker: string; label: string; value: string }) {
  return <section style={{ border: '1px solid var(--line)', padding: 16 }}><div className="marker">{marker}</div><strong className="number">{value}</strong><p>{label}</p></section>;
}
