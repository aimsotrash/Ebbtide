import { BrainCircuit, Zap, Target, Clock } from 'lucide-react';
import type { Category } from '@/lib/types';
import { categoryColors } from '@/styles/theme';

const CATEGORIES: Array<{ value: Category | 'all'; label: string }> = [
  { value: 'all', label: 'All categories' },
  { value: 'technical', label: 'Technical' },
  { value: 'personal', label: 'Personal' },
  { value: 'reference', label: 'Reference' },
  { value: 'general', label: 'General' },
];

interface QuizIntroProps {
  onStart: (category?: Category) => void;
  loading?: boolean;
}

export function QuizIntro({ onStart, loading }: QuizIntroProps) {
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="app-card p-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-center">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
            <BrainCircuit size={30} />
          </div>
          <div>
            <p className="app-label mb-2">Adaptive quiz mode</p>
            <h1 className="text-2xl font-extrabold text-[var(--text-1)]">Strengthen what is fading.</h1>
            <p className="mt-2 text-[var(--text-2)]">
              Dory generates questions from low-retention chunks. Correct answers boost stability; misses become review targets.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {[
          { icon: Target, label: 'Adaptive', sub: 'Targets weak chunks', color: 'var(--warn)' },
          { icon: Zap, label: 'Retention boost', sub: 'Reviews update stability', color: 'var(--accent)' },
          { icon: Clock, label: 'Fast session', sub: 'A few focused minutes', color: 'var(--info)' },
        ].map(({ icon: Icon, label, sub, color }) => (
          <div key={label} className="app-card p-4">
            <Icon size={18} style={{ color }} />
            <p className="mt-3 font-bold text-[var(--text-1)]">{label}</p>
            <p className="mt-1 text-sm text-[var(--text-3)]">{sub}</p>
          </div>
        ))}
      </div>

      <div className="app-card p-5">
        <p className="app-label mb-3">Choose focus area</p>
        <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-3">
          {CATEGORIES.map(({ value, label }) => {
            const color = value !== 'all' ? categoryColors[value] : 'var(--accent)';
            return (
              <button
                key={value}
                type="button"
                onClick={() => onStart(value === 'all' ? undefined : value)}
                disabled={loading}
                className="rounded-lg border px-4 py-3 text-sm font-bold transition hover:bg-[var(--surface-2)] disabled:opacity-50"
                style={{ color, borderColor: value === 'all' ? 'var(--accent-border)' : `color-mix(in oklab, ${color} 33%, transparent)`, background: value === 'all' ? 'var(--accent-soft)' : `color-mix(in oklab, ${color} 8%, transparent)` }}
              >
                {loading ? 'Loading...' : label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
