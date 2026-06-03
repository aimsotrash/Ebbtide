import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowLeft, CheckCircle2, Sparkles, X } from 'lucide-react';
import { getReviewQueue, gradeChunk } from '@/lib/api';
import type { Grade, ReviewCard } from '@/lib/types';

const GRADES: { value: Grade; label: string; shortcut: string; color: string; description: string }[] = [
  { value: 1, label: 'Again', shortcut: '1', color: 'var(--danger)', description: 'Forgot it' },
  { value: 2, label: 'Hard',  shortcut: '2', color: 'oklch(0.65 0.17 45)', description: 'Recalled with effort' },
  { value: 3, label: 'Good',  shortcut: '3', color: 'var(--warn)',  description: 'Recalled correctly' },
  { value: 4, label: 'Easy',  shortcut: '4', color: 'var(--good)',  description: 'Trivial' },
];

interface GradeStats {
  again: number;
  hard: number;
  good: number;
  easy: number;
}

function baseName(path: string) {
  return path.split(/[\\/]/).pop() ?? path;
}

/** Render "in 3 days" / "in 12 minutes" from an ISO date in the future. */
function timeUntil(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return 'now';
  const minutes = Math.round(ms / 60_000);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round(ms / 3_600_000);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(ms / 86_400_000);
  if (days < 30) return `${days}d`;
  const months = Math.round(days / 30);
  if (months < 12) return `${months}mo`;
  return `${Math.round(days / 365)}y`;
}

export function ReviewPage() {
  const navigate = useNavigate();
  const [queue, setQueue] = useState<ReviewCard[] | null>(null); // null = loading
  const [position, setPosition] = useState(0); // index into queue
  const [stats, setStats] = useState<GradeStats>({ again: 0, hard: 0, good: 0, easy: 0 });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalDue, setTotalDue] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1); // for slide animation
  const [lastFeedback, setLastFeedback] = useState<{ grade: Grade; nextDue: string } | null>(null);

  // Load queue once on mount.
  useEffect(() => {
    let cancelled = false;
    getReviewQueue(50)
      .then(r => {
        if (cancelled) return;
        setQueue(r.cards);
        setTotalDue(r.due_count);
      })
      .catch(e => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Could not load review queue.');
        setQueue([]);
      });
    return () => { cancelled = true; };
  }, []);

  const current = queue && position < queue.length ? queue[position] : null;
  const finished = queue !== null && (queue.length === 0 || position >= queue.length);
  const reviewedCount = stats.again + stats.hard + stats.good + stats.easy;

  const submit = useCallback(async (grade: Grade) => {
    if (!current || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await gradeChunk(current.chunk_id, grade);
      setStats(s => ({
        again: s.again + (grade === 1 ? 1 : 0),
        hard:  s.hard  + (grade === 2 ? 1 : 0),
        good:  s.good  + (grade === 3 ? 1 : 0),
        easy:  s.easy  + (grade === 4 ? 1 : 0),
      }));
      setLastFeedback({ grade, nextDue: result.next_due });
      setDirection(1);
      setPosition(p => p + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Grading failed.');
    } finally {
      setSubmitting(false);
    }
  }, [current, submitting]);

  // Auto-clear the "next due in X" feedback after a short window.
  useEffect(() => {
    if (!lastFeedback) return;
    const t = setTimeout(() => setLastFeedback(null), 2200);
    return () => clearTimeout(t);
  }, [lastFeedback]);

  // Keyboard shortcuts: 1-4 to grade, Esc to exit.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Skip when user is typing in an input.
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;

      if (e.key === 'Escape') {
        navigate('/');
        return;
      }
      if (!current) return;
      const grade = ['1', '2', '3', '4'].indexOf(e.key);
      if (grade >= 0) {
        e.preventDefault();
        void submit((grade + 1) as Grade);
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [current, submit, navigate]);

  const progress = useMemo(() => {
    if (!queue || queue.length === 0) return 0;
    return Math.round((position / queue.length) * 100);
  }, [queue, position]);

  // ── Loading state ─────────────────────────────────────────────────
  if (queue === null) {
    return (
      <div className="mx-auto max-w-2xl py-10 text-center text-sm text-[var(--text-3)]">
        Loading review queue…
      </div>
    );
  }

  // ── Empty state ───────────────────────────────────────────────────
  if (queue.length === 0) {
    return (
      <div className="mx-auto max-w-md py-10">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-8 text-center">
          <CheckCircle2 size={36} className="mx-auto text-[var(--good)]" />
          <p className="mt-3 text-lg font-bold text-[var(--text-1)]">All caught up</p>
          <p className="mt-1 text-sm text-[var(--text-3)]">
            No memories are due for review right now. Come back tomorrow.
          </p>
          <Link to="/" className="btn-primary mt-5 inline-flex">
            <ArrowLeft size={14} /> Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  // ── End-of-session screen ─────────────────────────────────────────
  if (finished) {
    const tomorrow = Math.max(0, totalDue - reviewedCount);
    return (
      <div className="mx-auto max-w-md py-10">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-8">
          <div className="text-center">
            <Sparkles size={36} className="mx-auto text-[var(--accent)]" />
            <p className="mt-3 text-2xl font-extrabold text-[var(--text-1)]">Session complete</p>
            <p className="mt-1 text-sm text-[var(--text-3)]">
              You reviewed <span className="font-bold text-[var(--text-1)]">{reviewedCount}</span> memor{reviewedCount === 1 ? 'y' : 'ies'}.
            </p>
          </div>

          <div className="mt-6 grid grid-cols-4 gap-2">
            {GRADES.map(g => {
              const count = (
                g.value === 1 ? stats.again :
                g.value === 2 ? stats.hard :
                g.value === 3 ? stats.good :
                stats.easy
              );
              return (
                <div key={g.value} className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 text-center">
                  <div className="text-xs font-bold uppercase tracking-wide" style={{ color: g.color }}>{g.label}</div>
                  <div className="mt-1 text-2xl font-extrabold text-[var(--text-1)]">{count}</div>
                </div>
              );
            })}
          </div>

          <div className="mt-6 rounded-lg bg-[var(--surface-2)] p-3 text-center text-sm">
            <span className="text-[var(--text-3)]">More due later: </span>
            <span className="font-bold text-[var(--text-1)]">{tomorrow}</span>
          </div>

          <div className="mt-6 flex gap-2">
            <Link to="/" className="btn-secondary flex-1 justify-center">
              <ArrowLeft size={14} /> Dashboard
            </Link>
            {tomorrow > 0 && (
              <button
                type="button"
                onClick={() => { setStats({ again: 0, hard: 0, good: 0, easy: 0 }); setPosition(0); void getReviewQueue(50).then(r => { setQueue(r.cards); setTotalDue(r.due_count); }); }}
                className="btn-primary flex-1 justify-center"
              >
                Keep going
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── Active review card ────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-2xl py-6">
      {/* Header: progress bar + exit */}
      <div className="mb-4 flex items-center gap-4">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="btn-ghost p-2"
          aria-label="Exit review"
          title="Exit (Esc)"
        >
          <X size={16} />
        </button>

        <div className="flex-1">
          <div className="mb-1 flex items-center justify-between text-xs font-bold text-[var(--text-3)]">
            <span>{position + 1} of {queue.length}</span>
            <span>{reviewedCount} reviewed</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-[var(--surface-3)]">
            <motion.div
              className="h-full rounded-full bg-[var(--accent)]"
              animate={{ width: `${progress}%` }}
              transition={{ type: 'spring', stiffness: 180, damping: 22 }}
            />
          </div>
        </div>
      </div>

      {error && (
        <p className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>
      )}

      {/* Next-due feedback toast for the card you just graded */}
      <AnimatePresence>
        {lastFeedback && (
          <motion.div
            key={lastFeedback.nextDue}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18 }}
            className="mb-3 flex items-center justify-center gap-2 rounded-lg border border-[var(--accent-border)] bg-[var(--accent-soft)] px-3 py-2 text-xs font-medium text-[var(--text-2)]"
          >
            <Sparkles size={13} className="text-[var(--accent)]" />
            <span><span className="font-bold text-[var(--text-1)]">{GRADES[lastFeedback.grade - 1].label}</span>. Next review in <span className="font-bold text-[var(--text-1)]">{timeUntil(lastFeedback.nextDue)}</span>.</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Card */}
      <AnimatePresence mode="wait" custom={direction}>
        {current && (
          <motion.div
            key={current.chunk_id}
            custom={direction}
            initial={{ opacity: 0, x: direction * 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: direction * -30 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="app-card p-7"
          >
            <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--text-3)]">
              <span>{baseName(current.source_file)}</span>
              {current.category && (
                <>
                  <span>·</span>
                  <span>{current.category}</span>
                </>
              )}
            </div>
            <p className="whitespace-pre-wrap text-base leading-relaxed text-[var(--text-1)]">
              {current.content}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Grade prompt */}
      <p className="mt-6 text-center text-sm text-[var(--text-3)]">
        How well did you remember this?
      </p>

      {/* Grade buttons — wraps to 2x2 on small screens */}
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {GRADES.map(g => (
          <button
            key={g.value}
            type="button"
            onClick={() => void submit(g.value)}
            disabled={submitting}
            className="group flex flex-col items-center justify-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] py-3 min-h-[68px] transition-all hover:-translate-y-0.5 hover:shadow-md active:translate-y-0 disabled:cursor-wait disabled:opacity-50"
            style={{ borderTopColor: g.color, borderTopWidth: 3 }}
          >
            <span className="text-sm font-bold" style={{ color: g.color }}>{g.label}</span>
            <span className="hidden sm:block text-[10px] text-[var(--text-3)]">{g.description}</span>
            <kbd className="hidden sm:block mt-0.5 rounded border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-3)]">
              {g.shortcut}
            </kbd>
          </button>
        ))}
      </div>

      <p className="mt-4 hidden sm:block text-center text-[10px] text-[var(--text-4)]">
        Press <kbd className="rounded bg-[var(--surface-2)] px-1 font-mono">1</kbd>–<kbd className="rounded bg-[var(--surface-2)] px-1 font-mono">4</kbd> to grade, <kbd className="rounded bg-[var(--surface-2)] px-1 font-mono">Esc</kbd> to exit
      </p>
    </div>
  );
}
