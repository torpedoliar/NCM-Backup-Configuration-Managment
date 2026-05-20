export function number(value: number | undefined): string {
  return (value ?? 0).toLocaleString();
}
