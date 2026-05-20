import type { ProblemDetails } from '../api/types';

export function ProblemToast({ problem }: { problem: ProblemDetails | null }) {
  if (!problem) return null;
  return <div role="alert" style={{ border: '1px solid var(--red)', padding: 12 }}><span className="marker">/ERR-{problem.type}</span><p>{problem.detail}</p></div>;
}
