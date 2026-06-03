import { Trophy, Zap, RotateCcw, CheckCircle2, XCircle, TrendingUp, TrendingDown } from 'lucide-react';
import type { QuizResults as QuizResultsType, QuizSession } from '@/lib/types';
import { cn } from '@/lib/utils';

interface QuizResultsProps {
  results: QuizResultsType;
  session: QuizSession;
  onRestart: () => void;
}

export function QuizResults({ results, session, onRestart }: QuizResultsProps) {
  const pct = Math.round((results.score / results.total) * 100);
  const grade =
    pct >= 90 ? { label: 'Excellent', color: 'var(--good)' } :
    pct >= 70 ? { label: 'Strong session', color: 'var(--accent)' } :
    pct >= 50 ? { label: 'Keep reviewing', color: 'var(--warn)' } :
    { label: 'Needs attention', color: 'var(--danger)' };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="app-card p-6 text-center">
        <Trophy size={38} className="mx-auto" style={{ color: grade.color }} />
        <h2 className="mt-3 text-2xl font-extrabold" style={{ color: grade.color }}>{grade.label}</h2>
        <p className="mt-1 text-sm text-[var(--text-3)]">{results.score} of {results.total} correct</p>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <div className="app-card-muted p-4">
            <p className="text-3xl font-extrabold text-[var(--text-1)]">{pct}%</p>
            <p className="text-sm text-[var(--text-3)]">Score</p>
          </div>
          <div className="app-card-muted p-4">
            <p className="inline-flex items-center gap-1 text-3xl font-extrabold text-[var(--accent)]"><Zap size={20} /> {results.xp_earned}</p>
            <p className="text-sm text-[var(--text-3)]">XP earned</p>
          </div>
          <div className="app-card-muted p-4">
            <p className="inline-flex items-center gap-1 text-3xl font-extrabold text-[var(--warn)]"><Trophy size={20} /> {results.streaks}</p>
            <p className="text-sm text-[var(--text-3)]">Streak</p>
          </div>
        </div>
      </div>

      <div className="app-card p-5">
        <p className="app-label mb-3">Answer review</p>
        <div className="space-y-2">
          {results.results.map((result, index) => {
            const question = session.questions[index];
            if (!question) return null;
            return (
              <div
                key={result.question_id}
                className={cn(
                  'flex items-start gap-3 rounded-lg border p-3',
                  result.correct
                    ? 'border-[color-mix(in_oklab,var(--good)_25%,transparent)] bg-[color-mix(in_oklab,var(--good)_8%,transparent)]'
                    : 'border-destructive/25 bg-destructive/10'
                )}
              >
                {result.correct ? <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-[var(--good)]" /> : <XCircle size={17} className="mt-0.5 shrink-0 text-[var(--danger)]" />}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold leading-relaxed text-[var(--text-1)]">{question.question}</p>
                  {!result.correct && <p className="mt-1 text-sm text-[var(--good)]">Correct answer: {question.options[result.correct_index]}</p>}
                </div>
                <span className={result.stability_delta > 0 ? 'tag badge-strong' : 'tag badge-critical'}>
                  {result.stability_delta > 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                  {result.stability_delta > 0 ? '+' : ''}{result.stability_delta}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <button type="button" onClick={onRestart} className="btn-primary w-full">
        <RotateCcw size={15} /> Quiz again
      </button>
    </div>
  );
}
