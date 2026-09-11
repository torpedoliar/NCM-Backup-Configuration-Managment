import { useEffect, useMemo, useState } from 'react';
import {
  downloadComplianceReport,
  fetchReviewDiff,
  fetchReviewRollbackScript,
  useAddReviewNote,
  useCompliance,
  useNotifySettings,
  usePromoteReviewToBaseline,
  useReviews,
  useReviewStatus,
  useRunFleetReviewCycle,
  useSendReviewReminder,
  useStartReview,
} from '../api/hooks';
import type { ConfigReviewStatus, FleetCycleAttestationResult, ReviewFilters } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';
import { humanizeError } from '../lib/errors';

const STATUS_LABEL: Record<string, string> = {
  pending: 'PENDING',
  in_review: 'IN REVIEW',
  approved: 'APPROVED',
  flagged: 'FLAGGED',
  dismissed: 'DISMISSED',
};

type DiffCategory = 'all' | 'vlan' | 'interface' | 'security' | 'system';
type DiffViewStyle = 'side-by-side' | 'unified';

interface SideBySideLine {
  lineA: number | null;
  textA: string;
  lineB: number | null;
  textB: string;
  type: 'equal' | 'delete' | 'insert' | 'replace';
  category: DiffCategory;
}

function classifyLine(text: string): DiffCategory {
  const lower = text.toLowerCase().trim();
  if (lower.includes('vlan')) return 'vlan';
  if (
    lower.startsWith('interface ') ||
    lower.startsWith('switchport ') ||
    lower.startsWith('ip address ') ||
    lower.startsWith('shutdown') ||
    lower.startsWith('no shutdown') ||
    lower.startsWith('speed ') ||
    lower.startsWith('duplex ') ||
    lower.startsWith('spanning-tree ')
  )
    return 'interface';
  if (
    lower.includes('access-list') ||
    lower.includes('acl') ||
    lower.includes('radius') ||
    lower.includes('tacacs') ||
    lower.includes('aaa ') ||
    lower.includes('crypto ') ||
    lower.includes('ssh ') ||
    lower.includes('password ') ||
    lower.includes('secret ') ||
    lower.includes('snmp-server community')
  )
    return 'security';
  if (
    lower.startsWith('hostname ') ||
    lower.startsWith('ntp ') ||
    lower.startsWith('clock ') ||
    lower.startsWith('service ') ||
    lower.startsWith('logging ') ||
    lower.startsWith('banner ')
  )
    return 'system';
  return 'all';
}

function parseUnifiedDiffToSideBySide(rawDiff: string, hideNoise: boolean): SideBySideLine[] {
  const lines = rawDiff.split('\n');
  const rows: SideBySideLine[] = [];
  let lineA = 1;
  let lineB = 1;

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith('---') || line.startsWith('+++')) {
      i++;
      continue;
    }
    const hunkMatch = line.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
    if (hunkMatch) {
      lineA = parseInt(hunkMatch[1], 10);
      lineB = parseInt(hunkMatch[2], 10);
      i++;
      continue;
    }

    if (line.startsWith('-')) {
      const deletes: string[] = [];
      while (i < lines.length && lines[i].startsWith('-')) {
        deletes.push(lines[i].slice(1));
        i++;
      }
      const inserts: string[] = [];
      while (i < lines.length && lines[i].startsWith('+')) {
        inserts.push(lines[i].slice(1));
        i++;
      }

      const maxLen = Math.max(deletes.length, inserts.length);
      for (let k = 0; k < maxLen; k++) {
        const delText = deletes[k] ?? '';
        const insText = inserts[k] ?? '';

        if (hideNoise) {
          const checkNoise = (delText + ' ' + insText).toLowerCase();
          if (
            checkNoise.includes('ntp clock-period') ||
            checkNoise.includes('uptime') ||
            checkNoise.includes('last configuration change') ||
            checkNoise.includes('nvram config last updated')
          ) {
            if (k < deletes.length) lineA++;
            if (k < inserts.length) lineB++;
            continue;
          }
        }

        const cat = classifyLine(delText || insText);

        if (k < deletes.length && k < inserts.length) {
          rows.push({
            lineA: lineA++,
            textA: delText,
            lineB: lineB++,
            textB: insText,
            type: 'replace',
            category: cat,
          });
        } else if (k < deletes.length) {
          rows.push({
            lineA: lineA++,
            textA: delText,
            lineB: null,
            textB: '',
            type: 'delete',
            category: cat,
          });
        } else {
          rows.push({
            lineA: null,
            textA: '',
            lineB: lineB++,
            textB: insText,
            type: 'insert',
            category: cat,
          });
        }
      }
      continue;
    }

    if (line.startsWith('+')) {
      const insText = line.slice(1);
      if (
        !hideNoise ||
        (!insText.toLowerCase().includes('ntp clock-period') &&
          !insText.toLowerCase().includes('last configuration change'))
      ) {
        rows.push({
          lineA: null,
          textA: '',
          lineB: lineB++,
          textB: insText,
          type: 'insert',
          category: classifyLine(insText),
        });
      } else {
        lineB++;
      }
      i++;
      continue;
    }

    if (line.startsWith(' ')) {
      const eqText = line.slice(1);
      rows.push({
        lineA: lineA++,
        textA: eqText,
        lineB: lineB++,
        textB: eqText,
        type: 'equal',
        category: classifyLine(eqText),
      });
      i++;
      continue;
    }

    i++;
  }
  return rows;
}

function summaryText(summary: Record<string, unknown>): string {
  const parts: string[] = [];
  const added = summary.vlans_added as number[] | undefined;
  const removed = summary.vlans_removed as number[] | undefined;
  const changed = summary.ports_changed as string[] | undefined;
  if (added?.length) parts.push(`VLAN +${added.join(',')}`);
  if (removed?.length) parts.push(`VLAN -${removed.join(',')}`);
  if (changed?.length) parts.push(`${changed.length} port(s) changed (${changed.slice(0, 5).join(', ')})`);
  if (summary.hostname_changed) parts.push('hostname changed');
  return parts.join(' · ') || 'text diff only';
}

function CompliancePanel({
  onTriggerCycle,
  isTriggering,
  onSendReminder,
  isSendingReminder,
}: {
  onTriggerCycle: () => void;
  isTriggering: boolean;
  onSendReminder: () => void;
  isSendingReminder: boolean;
}) {
  const { data } = useCompliance();
  const { data: notifySettings } = useNotifySettings();
  if (!data) return null;
  const coverage =
    data.switches_total > 0
      ? Math.round((data.switches_with_baseline / data.switches_total) * 100)
      : 0;

  const reminderHour = String(notifySettings?.review_reminder_hour ?? 9).padStart(2, '0');
  const reminderMinute = String(notifySettings?.review_reminder_minute ?? 0).padStart(2, '0');
  const emailEnabled = notifySettings?.enabled && notifySettings?.email_enabled;

  return (
    <section className="settings-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h3>Compliance overview (ISO 27001 A.8.9)</h3>
          <p className="settings-help">
            Every switch needs a golden-config baseline; every drift from that baseline needs a review.
            This is the evidence trail for configuration management.
          </p>
        </div>
        <div style={{ textAlign: 'right', minWidth: '220px' }}>
          <span className={`badge ${emailEnabled ? 'state-ok' : 'state-warn'}`}>
            {emailEnabled ? 'EMAIL REMINDER ACTIVE' : 'EMAIL REMINDER DISABLED'}
          </span>
          <p className="settings-help" style={{ marginTop: '6px', fontSize: '11px' }}>
            Daily schedule: <b>{reminderHour}:{reminderMinute}</b> (Set in Baselines)
          </p>
        </div>
      </div>
      <div className="compliance-stats">
        <div>
          <span className="compliance-num">{coverage}%</span>
          <span className="compliance-label">baseline coverage</span>
        </div>
        <div>
          <span className="compliance-num">{data.reviews_pending}</span>
          <span className="compliance-label">reviews pending</span>
        </div>
        <div>
          <span className="compliance-num">{data.reviews_flagged}</span>
          <span className="compliance-label">flagged</span>
        </div>
        <div>
          <span className="compliance-num">{data.switches_missing_baseline.length}</span>
          <span className="compliance-label">switches without baseline</span>
        </div>
        <div>
          <span className="compliance-num">{data.baselines_stale.length}</span>
          <span className="compliance-label">reminder due (every {data.review_interval_months}mo)</span>
        </div>
      </div>
      {data.switches_missing_baseline.length > 0 ? (
        <p className="settings-help">
          Missing baselines: {data.switches_missing_baseline.join(', ')}. Create them on the
          Baselines page — drift detection is inactive for those switches until a baseline exists.
        </p>
      ) : null}
      {data.baselines_stale.length > 0 ? (
        <p className="settings-help">
          Reminder review due: {data.baselines_stale.join(', ')}. Refresh them on the Baselines page
          to re-attest against the current config and reset the cycle.
        </p>
      ) : null}
      <div className="row-actions" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button onClick={() => downloadComplianceReport('csv')}>Export CSV</button>
          <button onClick={() => downloadComplianceReport('xlsx')}>Export Excel</button>
          <button onClick={() => downloadComplianceReport('pdf')}>Export PDF</button>
          <button
            type="button"
            onClick={onSendReminder}
            disabled={isSendingReminder}
            title="Kirim email pengingat review pending & gap baseline ke administrator sekarang"
            style={{ borderColor: 'var(--blue, #3b82f6)', color: '#60a5fa' }}
          >
            {isSendingReminder ? 'Mengirim Reminder…' : '✉ Kirim Reminder Email'}
          </button>
        </div>
        <button
          type="button"
          onClick={onTriggerCycle}
          disabled={isTriggering}
          className="btn-primary"
          style={{
            background: 'rgba(255, 184, 0, 0.15)',
            borderColor: 'var(--amber)',
            color: 'var(--amber)',
            fontWeight: 'bold',
          }}
          title="Bandingkan seluruh switch ke baseline sekarang, reset siklus periode, dan kirim email hasil review"
        >
          {isTriggering ? 'Running Attestation…' : '⚡ Jalankan Siklus Review Sekarang (All Switches)'}
        </button>
      </div>
    </section>
  );
}

export function ConfigReviewPage() {
  const [filters, setFilters] = useState<ReviewFilters>({ include_notes: true });
  const { data: reviews = [] } = useReviews(filters);
  const update = useReviewStatus();
  const start = useStartReview();
  const addNote = useAddReviewNote();
  const promote = usePromoteReviewToBaseline();
  const runCycle = useRunFleetReviewCycle();
  const sendReminder = useSendReviewReminder();

  const [selected, setSelected] = useState<number | null>(null);
  const [diff, setDiff] = useState<string | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  // Cycle Modal state
  const [cycleModalOpen, setCycleModalOpen] = useState(false);
  const [cycleResult, setCycleResult] = useState<FleetCycleAttestationResult | null>(null);

  // Smart Diff controls
  const [viewStyle, setViewStyle] = useState<DiffViewStyle>('side-by-side');
  const [activeCategory, setActiveCategory] = useState<DiffCategory>('all');
  const [hideNoise, setHideNoise] = useState(false);

  // Promote Modal state
  const [promoteModalOpen, setPromoteModalOpen] = useState(false);
  const [promoteReviewId, setPromoteReviewId] = useState<number | null>(null);
  const [promoteReason, setPromoteReason] = useState('');
  const [promoteComment, setPromoteComment] = useState('');

  // Flag & Rollback Modal state
  const [rollbackModalOpen, setRollbackModalOpen] = useState(false);
  const [rollbackScript, setRollbackScript] = useState<string>('');
  const [rollbackLoading, setRollbackLoading] = useState(false);
  const [flagIncidentRef, setFlagIncidentRef] = useState('');

  const selectedReview = reviews.find((r) => r.id === selected) ?? null;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const idParam = params.get('id');
    if (idParam) {
      const num = Number(idParam);
      if (!Number.isNaN(num)) {
        setSelected(num);
      }
    }
  }, []);

  useEffect(() => {
    if (selected === null) return;
    let cancelled = false;
    setDiff(null);
    setDiffError(null);
    fetchReviewDiff(selected)
      .then((t) => {
        if (!cancelled) setDiff(t);
      })
      .catch((err) => {
        if (!cancelled) setDiffError(err.message ?? 'Failed to load diff');
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const parsedDiffRows = useMemo(() => {
    if (!diff) return [];
    return parseUnifiedDiffToSideBySide(diff, hideNoise);
  }, [diff, hideNoise]);

  const isCleanMatch = useMemo(() => {
    if (diff === null) return false;
    return !diff.trim() || parsedDiffRows.every((r) => r.type === 'equal');
  }, [diff, parsedDiffRows]);

  const filteredDiffRows = useMemo(() => {
    if (activeCategory === 'all') return parsedDiffRows;
    return parsedDiffRows.filter((r) => r.type !== 'equal' && r.category === activeCategory);
  }, [parsedDiffRows, activeCategory]);

  function decide(reviewId: number, status: ConfigReviewStatus, defaultComment?: string) {
    if (status === 'flagged') {
      setPromoteReviewId(reviewId);
      setFlagIncidentRef('');
      setRollbackModalOpen(true);
      setRollbackLoading(true);
      fetchReviewRollbackScript(reviewId)
        .then((script) => setRollbackScript(script))
        .catch(() => setRollbackScript('! Failed to fetch rollback script from server.'))
        .finally(() => setRollbackLoading(false));
      return;
    }

    const comment =
      window.prompt(
        status === 'approved'
          ? `Konfirmasi Approve untuk review #${reviewId}? Masukkan catatan/justifikasi verifikasi:`
          : `Keputusan ${status} untuk review #${reviewId}? (opsional, catatan bisa ditambah di thread)`,
        defaultComment ?? '',
      ) ?? undefined;

    if (comment === undefined) return;

    setActionError(null);
    update.mutate(
      { id: reviewId, status, comment: comment || defaultComment, reset_baseline_cycle: true },
      {
        onError: (err: unknown) => setActionError(humanizeError(err)),
      },
    );
  }

  function openPromoteModal(reviewId: number) {
    setPromoteReviewId(reviewId);
    setPromoteReason('');
    setPromoteComment('');
    setPromoteModalOpen(true);
    setActionError(null);
  }

  function handlePromoteSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!promoteReviewId || !promoteReason.trim()) return;
    promote.mutate(
      {
        id: promoteReviewId,
        reason: promoteReason.trim(),
        comment: promoteComment.trim() || undefined,
      },
      {
        onSuccess: () => {
          setPromoteModalOpen(false);
          setPromoteReason('');
          setPromoteComment('');
        },
        onError: (err: unknown) => setActionError(humanizeError(err)),
      },
    );
  }

  function handleFlagSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!promoteReviewId) return;
    const comment = flagIncidentRef.trim()
      ? `[FLAGGED - Remediation Required] ${flagIncidentRef.trim()}`
      : '[FLAGGED - Remediation Required] Unapproved drift';
    update.mutate(
      { id: promoteReviewId, status: 'flagged', comment },
      {
        onSuccess: () => {
          setRollbackModalOpen(false);
        },
        onError: (err: unknown) => setActionError(humanizeError(err)),
      },
    );
  }

  function submitNote(reviewId: number) {
    const body = noteDraft.trim();
    if (!body) return;
    setActionError(null);
    addNote.mutate(
      { id: reviewId, body },
      {
        onSuccess: () => setNoteDraft(''),
        onError: (err: unknown) => setActionError(humanizeError(err)),
      },
    );
  }

  function handleTriggerCycle() {
    if (!window.confirm('Jalankan siklus review sekarang untuk seluruh switch? Semua switch yang identik dengan baseline akan di-reset siklusnya, dan hasil audit akan dikirim via email.')) {
      return;
    }
    setActionError(null);
    runCycle.mutate(undefined, {
      onSuccess: (res) => {
        setCycleResult(res);
        setCycleModalOpen(true);
      },
      onError: (err: unknown) => setActionError(humanizeError(err)),
    });
  }

  function handleSendReminder() {
    if (!window.confirm('Kirim email reminder status review pending & gap baseline ke administrator sekarang?')) {
      return;
    }
    setActionError(null);
    sendReminder.mutate(undefined, {
      onSuccess: (res) => {
        alert(res.message);
      },
      onError: (err: unknown) => setActionError(humanizeError(err)),
    });
  }

  return (
    <main>
      <p className="marker">/08 · REVIEW</p>
      <h1 className="headline">Config changes, reviewed.</h1>
      <p className="muted">
        Workflow: define a golden-config baseline → every backup is compared against it → any drift
        opens a review here → approve, promote to new baseline, or flag with rollback guidance. All
        logged as ISO 27001 A.8.9 evidence.
      </p>

      <CompliancePanel
        onTriggerCycle={handleTriggerCycle}
        isTriggering={runCycle.isPending}
        onSendReminder={handleSendReminder}
        isSendingReminder={sendReminder.isPending}
      />

      <section className="filter-bar">
        <label>
          Status
          <select
            value={filters.status ?? ''}
            onChange={(e) =>
              setFilters({
                ...filters,
                status: (e.target.value || undefined) as ConfigReviewStatus | undefined,
              })
            }
          >
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="in_review">In Review</option>
            <option value="approved">Approved</option>
            <option value="flagged">Flagged</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </label>
      </section>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Switch</th>
              <th>Created</th>
              <th>Status</th>
              <th>Reviewer</th>
              <th>Summary</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {reviews.map((r) => (
              <tr key={r.id}>
                <td>#{r.id}</td>
                <td>{r.switch_name ?? `#${r.switch_id}`}</td>
                <td>{formatTzDateTime(r.created_at)}</td>
                <td>
                  <span
                    className={`badge state-${
                      r.status === 'flagged' ? 'fail' : r.status === 'approved' ? 'ok' : 'warn'
                    }`}
                  >
                    {STATUS_LABEL[r.status] ?? r.status}
                  </span>
                </td>
                <td>
                  {r.reviewed_by_name ? (
                    <span style={{ fontWeight: 600, color: 'var(--amber, #f59e0b)' }} title={`Reviewer ID: ${r.reviewed_by}`}>
                      {r.reviewed_by_name}
                    </span>
                  ) : r.started_by_name ? (
                    <span style={{ color: 'var(--muted, #94a3b8)', fontStyle: 'italic', fontSize: '11px' }} title={`Started by ID: ${r.started_by}`}>
                      in review: {r.started_by_name}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--muted, #94a3b8)' }}>-</span>
                  )}
                </td>
                <td title={JSON.stringify(r.diff_summary)}>{summaryText(r.diff_summary)}</td>
                <td className="row-actions">
                  <button onClick={() => setSelected(selected === r.id ? null : r.id)}>Diff</button>
                  {r.status === 'pending' ? (
                    <button
                      onClick={() => {
                        setActionError(null);
                        start.mutate(r.id, {
                          onError: (err: unknown) => setActionError(humanizeError(err)),
                        });
                      }}
                      disabled={start.isPending}
                      title="Ambil review ini untuk dikerjakan — status menjadi In Review"
                    >
                      Mulai Review
                    </button>
                  ) : r.status === 'in_review' ? (
                    <>
                      <button
                        onClick={() => openPromoteModal(r.id)}
                        className="btn-primary"
                        style={{ color: 'var(--amber)', fontWeight: 'bold' }}
                        title="Approve and promote this backup as the new golden baseline"
                      >
                        ★ Promote
                      </button>
                      <button
                        onClick={() => decide(r.id, 'approved', 'Approve drift operasional, pertahankan baseline lama')}
                        style={{ color: '#60a5fa' }}
                        title="Setujui perubahan ini tetapi pertahankan golden baseline lama"
                      >
                        ✓ Keep Old
                      </button>
                      <button onClick={() => decide(r.id, 'flagged')}>Flag &amp; Remediate</button>
                      <button onClick={() => decide(r.id, 'dismissed')}>Dismiss</button>
                    </>
                  ) : (
                    <span className="marker">{r.comment ? 'has comment' : ''}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {reviews.length === 0 ? <p className="viewer-empty">No reviews match the filter.</p> : null}
      </div>

      {selected !== null ? (
        <section className="viewer-box" aria-label="Review diff viewer">
          <header className="viewer-box-header" style={{ alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span className="marker">REVIEW #{selected} · {selectedReview?.switch_name} · DIFF &amp; INSPECTION</span>
              <div style={{ fontSize: '12px', color: 'var(--muted, #94a3b8)', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                <span>Golden Baseline: <strong>#{selectedReview?.baseline_backup_id ?? selectedReview?.baseline_id ?? '?'}</strong></span>
                <span>Detected Backup: <strong>#{selectedReview?.backup_id}</strong></span>
                {selectedReview?.reviewed_by_name ? (
                  <span>Reviewer: <strong style={{ color: 'var(--amber)' }}>{selectedReview.reviewed_by_name}</strong> ({formatTzDateTime(selectedReview.reviewed_at)})</span>
                ) : selectedReview?.started_by_name ? (
                  <span>In Review by: <strong style={{ color: '#60a5fa' }}>{selectedReview.started_by_name}</strong> ({formatTzDateTime(selectedReview.started_at)})</span>
                ) : (
                  <span>Status: <strong style={{ color: 'var(--amber)' }}>{selectedReview?.status.toUpperCase()}</strong></span>
                )}
                {selectedReview?.comment ? (
                  <span>Catatan: <em>{selectedReview.comment}</em></span>
                ) : null}
              </div>
            </div>
            <div className="row-actions">
              {selectedReview?.status === 'pending' ? (
                <button
                  onClick={() =>
                    start.mutate(selected, {
                      onError: (err: unknown) => setActionError(humanizeError(err)),
                    })
                  }
                  disabled={start.isPending}
                >
                  Mulai Review
                </button>
              ) : selectedReview?.status === 'in_review' ? (
                <>
                  {isCleanMatch ? (
                    <button
                      onClick={() => decide(selected, 'approved', 'Konfirmasi sesuai: konfigurasi identik dengan baseline (tanpa drift)')}
                      className="btn-primary"
                      style={{ color: '#34d399', borderColor: '#10b981', fontWeight: 'bold' }}
                    >
                      ✓ Konfirmasi Sesuai (Attest Clean &amp; Reset Siklus)
                    </button>
                  ) : (
                    <>
                      <button
                        onClick={() => openPromoteModal(selected)}
                        style={{ color: 'var(--amber)', fontWeight: 'bold' }}
                        title="Setujui dan jadikan konfigurasi backup terbaru ini sebagai Golden Baseline baru"
                      >
                        ★ Approve &amp; Promote to Baseline
                      </button>
                      <button
                        onClick={() => decide(selected, 'approved', 'Approve drift operasional, pertahankan baseline lama')}
                        style={{ color: '#60a5fa', borderColor: 'var(--blue, #3b82f6)' }}
                        title="Setujui perubahan ini tetapi pertahankan golden baseline lama"
                      >
                        ✓ Approve &amp; Pertahankan Baseline Lama
                      </button>
                      <button onClick={() => decide(selected, 'flagged')}>Flag &amp; Remediate</button>
                    </>
                  )}
                </>
              ) : null}
              <button onClick={() => setSelected(null)}>Close</button>
            </div>
          </header>

          {/* Clean Match Banner when 0 diff */}
          {isCleanMatch && (
            <div style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '6px', margin: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <h4 style={{ margin: 0, color: '#34d399', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '18px' }}>✓</span> Konfigurasi 100% Identik (Tidak Ada Drift)
                </h4>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--bone)' }}>
                  Konfigurasi backup terakhir switch ini sesuai sepenuhnya dengan Golden Baseline. Tidak ada perubahan konfigurasi yang memerlukan remedi.
                </p>
              </div>
              {selectedReview?.status === 'in_review' ? (
                <button
                  type="button"
                  onClick={() => decide(selected, 'approved', 'Konfirmasi sesuai: konfigurasi identik dengan baseline (tanpa drift)')}
                  className="btn-primary"
                  style={{ color: '#34d399', borderColor: '#10b981', fontWeight: 'bold' }}
                >
                  ✓ Konfirmasi Sesuai (Attest Clean &amp; Reset Siklus)
                </button>
              ) : null}
            </div>
          )}

          {/* Smart Diff Toolbar */}
          <div
            style={{
              padding: '10px 16px',
              background: 'rgba(255,255,255,0.02)',
              borderBottom: '1px solid var(--line)',
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span className="marker" style={{ marginRight: '6px' }}>
                VIEW:
              </span>
              <button
                type="button"
                className={`chip ${viewStyle === 'side-by-side' ? 'active' : ''}`}
                onClick={() => setViewStyle('side-by-side')}
              >
                Side-by-Side Split
              </button>
              <button
                type="button"
                className={`chip ${viewStyle === 'unified' ? 'active' : ''}`}
                onClick={() => setViewStyle('unified')}
              >
                Unified Raw
              </button>
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12px',
                  marginLeft: '12px',
                  cursor: 'pointer',
                  color: 'var(--bone)',
                }}
              >
                <input
                  type="checkbox"
                  checked={hideNoise}
                  onChange={(e) => setHideNoise(e.target.checked)}
                />
                Hide Noise (NTP/Uptime)
              </label>
            </div>

            {viewStyle === 'side-by-side' ? (
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                <span className="marker" style={{ marginRight: '6px' }}>
                  FILTER:
                </span>
                {(
                  [
                    ['all', 'All Changes'],
                    ['vlan', 'VLANs'],
                    ['interface', 'Interfaces'],
                    ['security', 'Security & AAA'],
                    ['system', 'System/Host'],
                  ] as const
                ).map(([cat, label]) => (
                  <button
                    key={cat}
                    type="button"
                    className={`chip ${activeCategory === cat ? 'active' : ''}`}
                    onClick={() => setActiveCategory(cat)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          {selectedReview?.status === 'in_review' && selectedReview.started_at ? (
            <p className="settings-help" style={{ padding: '8px 16px' }}>
              Sedang direview (dimulai {formatTzDateTime(selectedReview.started_at)}). Tambahkan
              catatan di thread di bawah, atau pilih <b>Approve & Promote to Baseline</b> jika perubahan
              sah untuk ISO 27001.
            </p>
          ) : null}

          {diffError ? <p role="alert" className="viewer-empty">{diffError}</p> : null}
          {selected !== null && diff === null && !diffError ? (
            <p className="viewer-empty">Loading…</p>
          ) : null}

          {/* Diff Representation */}
          {diff !== null && viewStyle === 'unified' ? (
            <pre className="viewer-pre">{diff}</pre>
          ) : null}

          {diff !== null && viewStyle === 'side-by-side' ? (
            <div style={{ overflowX: 'auto', maxHeight: '550px' }}>
              <div className="diff-pane-headers">
                <div className="diff-pane-label">
                  GOLDEN BASELINE (Target State)
                </div>
                <div className="diff-pane-label">
                  CURRENT RUNNING CONFIG (Detected State)
                </div>
              </div>
              <div className="diff-grid" role="table" aria-label="Side by side diff">
                {filteredDiffRows.map((row, idx) => (
                  <div key={idx} className={`diff-row diff-row-${row.type}`} role="row">
                    <span className="diff-line-no" role="cell">
                      {row.lineA ?? ''}
                    </span>
                    <pre className="diff-text diff-text-a" role="cell">
                      {row.textA}
                    </pre>
                    <span className="diff-line-no" role="cell">
                      {row.lineB ?? ''}
                    </span>
                    <pre className="diff-text diff-text-b" role="cell">
                      {row.textB}
                    </pre>
                  </div>
                ))}
                {filteredDiffRows.length === 0 ? (
                  <p className="viewer-empty">No differences in this category filter.</p>
                ) : null}
              </div>
            </div>
          ) : null}

          {/* Audit Notes Thread */}
          <div style={{ padding: '0 16px 16px' }}>
            <h3>Audit Notes & Evidence Trail ({selectedReview?.notes.length ?? 0})</h3>
            <div className="review-notes">
              {(selectedReview?.notes ?? []).map((n) => (
                <div className="review-note" key={n.id}>
                  <span className="marker">
                    {n.author_name ?? `user-${n.author_id ?? '?'}`} · {formatTzDateTime(n.created_at)}
                  </span>
                  <p style={{ whiteSpace: 'pre-wrap' }}>{n.body}</p>
                </div>
              ))}
              {(selectedReview?.notes.length ?? 0) === 0 ? (
                <p className="viewer-empty">Belum ada catatan audit pada review ini.</p>
              ) : null}
            </div>
            <div className="review-note-form">
              <textarea
                rows={2}
                placeholder="Tambah catatan audit (mis. konfirmasi NOC, referensi tiket, justifikasi teknis)…"
                value={noteDraft}
                onChange={(e) => setNoteDraft(e.target.value)}
              />
              <button
                type="button"
                onClick={() => selected !== null && submitNote(selected)}
                disabled={addNote.isPending || !noteDraft.trim()}
              >
                {addNote.isPending ? 'Saving…' : 'Tambah catatan'}
              </button>
            </div>
          </div>

          {actionError ? <div role="alert" className="settings-error">{actionError}</div> : null}
        </section>
      ) : null}

      {/* MODAL: Approve & Promote to Baseline */}
      {promoteModalOpen && promoteReviewId !== null ? (
        <div className="modal-backdrop" onClick={() => setPromoteModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>★ Approve & Promote to Golden Baseline</h3>
            <p className="settings-help">
              Aksi ini akan menyetujui drift (status <b>APPROVED</b>) dan memperbarui golden
              baseline switch dengan config ini secara atomik. Siklus review berkala akan direset.
            </p>
            <form onSubmit={handlePromoteSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <label>
                Change Request ID / Authorization Justification (Wajib ISO 27001) *
                <input
                  type="text"
                  required
                  placeholder="e.g. CR-2026-089: Penambahan VLAN 20 untuk server finance"
                  value={promoteReason}
                  onChange={(e) => setPromoteReason(e.target.value)}
                  autoFocus
                />
              </label>
              <label>
                Additional Operational Comment (Opsional)
                <textarea
                  rows={3}
                  placeholder="Catatan verifikasi atau referensi personil pelaksana…"
                  value={promoteComment}
                  onChange={(e) => setPromoteComment(e.target.value)}
                />
              </label>
              <div className="row-actions" style={{ justifyContent: 'flex-end', marginTop: '10px' }}>
                <button type="button" onClick={() => setPromoteModalOpen(false)}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={promote.isPending || !promoteReason.trim()}
                  style={{ color: 'var(--amber)', fontWeight: 'bold' }}
                >
                  {promote.isPending ? 'Processing…' : 'Confirm & Promote to Baseline'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {/* MODAL: Flag & Rollback Remediation Guide */}
      {rollbackModalOpen && promoteReviewId !== null ? (
        <div className="modal-backdrop" onClick={() => setRollbackModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '720px' }}>
            <h3>⚠️ Flag Unapproved Drift & Rollback Guidance</h3>
            <p className="settings-help">
              Drift ini akan ditandai sebagai <b>FLAGGED</b> (temuan unapproved change untuk ISO 27001).
              Berikut adalah instruksi rollback CLI otomatis untuk remedi mengembalikan switch ke baseline.
            </p>

            <label>
              Incident / Violation Reference (Opsional)
              <input
                type="text"
                placeholder="e.g. INC-2026-401: Unauthorized VLAN creation on Core Switch"
                value={flagIncidentRef}
                onChange={(e) => setFlagIncidentRef(e.target.value)}
              />
            </label>

            <div>
              <span className="marker">REMEDIATION CLI ROLLBACK SCRIPT:</span>
              {rollbackLoading ? (
                <p className="viewer-empty">Generating script…</p>
              ) : (
                <pre className="viewer-pre" style={{ maxHeight: '220px', marginTop: '6px' }}>
                  {rollbackScript}
                </pre>
              )}
            </div>

            <div className="row-actions" style={{ justifyContent: 'space-between', marginTop: '10px' }}>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(rollbackScript);
                  alert('Rollback script copied to clipboard!');
                }}
              >
                Copy Script to Clipboard
              </button>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button type="button" onClick={() => setRollbackModalOpen(false)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  style={{ color: 'var(--amber)' }}
                  onClick={handleFlagSubmit}
                  disabled={update.isPending}
                >
                  {update.isPending ? 'Flagging…' : 'Confirm & Mark FLAGGED'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {/* MODAL: Fleet Cycle Attestation Result */}
      {cycleModalOpen && cycleResult ? (
        <div className="modal-backdrop" onClick={() => setCycleModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '680px' }}>
            <h3>⚡ Hasil Siklus Review Berkala (Attestation)</h3>
            <p className="settings-help">
              Pemeriksaan komparasi seluruh golden baseline vs running backup telah selesai.
              Laporan konfirmasi juga telah dikirim via email.
            </p>

            <div className="compliance-stats" style={{ gridTemplateColumns: 'repeat(3, 1fr)', margin: '12px 0' }}>
              <div>
                <span className="compliance-num">{cycleResult.total_checked}</span>
                <span className="compliance-label">total switch dicek</span>
              </div>
              <div>
                <span className="compliance-num" style={{ color: 'var(--state-ok, #2ecc71)' }}>
                  {cycleResult.clean_count}
                </span>
                <span className="compliance-label">clean (siklus direset)</span>
              </div>
              <div>
                <span className="compliance-num" style={{ color: cycleResult.drift_count > 0 ? 'var(--amber)' : 'inherit' }}>
                  {cycleResult.drift_count}
                </span>
                <span className="compliance-label">drift terdeteksi</span>
              </div>
            </div>

            {cycleResult.drift_details.length > 0 ? (
              <div>
                <h4 style={{ margin: '12px 0 6px', fontSize: '13px' }}>Switch Memerlukan Review:</h4>
                <div className="table-wrap" style={{ maxHeight: '180px' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Switch</th>
                        <th>Review ID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cycleResult.drift_details.map((d, i) => (
                        <tr key={i}>
                          <td>{d.switch_name}</td>
                          <td>#{d.review_id ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="viewer-empty" style={{ background: 'rgba(46, 204, 113, 0.1)', color: '#2ecc71', border: '1px solid rgba(46, 204, 113, 0.3)' }}>
                ✓ Seluruh switch 100% cocok dengan golden baseline. Jam siklus review ISO 27001 telah berhasil diperpanjang!
              </p>
            )}

            <div className="row-actions" style={{ justifyContent: 'flex-end', marginTop: '12px' }}>
              <button
                type="button"
                className="btn-primary"
                style={{ color: 'var(--amber)', fontWeight: 'bold' }}
                onClick={() => setCycleModalOpen(false)}
              >
                Tutup Ringkasan
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {runCycle.isError ? (
        <div role="alert" className="settings-error">
          {humanizeError(runCycle.error)}
        </div>
      ) : null}
      {update.isError ? (
        <div role="alert" className="settings-error">
          {humanizeError(update.error)}
        </div>
      ) : null}
      {promote.isError ? (
        <div role="alert" className="settings-error">
          {humanizeError(promote.error)}
        </div>
      ) : null}
    </main>
  );
}
