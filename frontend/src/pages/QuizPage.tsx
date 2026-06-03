import { useState, useCallback } from 'react';
import { QuizIntro } from '@/components/quiz/QuizIntro';
import { QuizQuestion } from '@/components/quiz/QuizQuestion';
import { QuizResults } from '@/components/quiz/QuizResults';
import { startQuiz, submitQuiz } from '@/lib/api';
import type { Category, QuizSession, QuizResults as QuizResultsType, QuizAnswer } from '@/lib/types';
import { BrainCircuit, CalendarClock, Target } from 'lucide-react';

type Phase = 'intro' | 'playing' | 'results';

export function QuizPage() {
  const [phase, setPhase] = useState<Phase>('intro');
  const [session, setSession] = useState<QuizSession | null>(null);
  const [results, setResults] = useState<QuizResultsType | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<QuizAnswer[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStart = useCallback(async (category?: Category) => {
    setLoading(true);
    setError(null);
    try {
      const s = await startQuiz(category);
      setSession(s);
      setCurrentIndex(0);
      setAnswers([]);
      setPhase('playing');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start quiz');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleAnswer = useCallback(async (selectedIndex: number, timeTakenMs: number) => {
    if (!session) return;
    const question = session.questions[currentIndex];
    if (!question) return;
    const nextAnswers = [
      ...answers,
      { question_id: question.id, selected_index: selectedIndex, time_taken_ms: timeTakenMs },
    ];
    setAnswers(nextAnswers);

    if (currentIndex + 1 < session.questions.length) {
      setCurrentIndex((i) => i + 1);
      return;
    }

    setLoading(true);
    try {
      const res = await submitQuiz(session.session_id, nextAnswers);
      try {
        const history = JSON.parse(localStorage.getItem('dory_quiz_history') ?? '[]');
        history.push({
          score: res.score,
          total: res.total,
          date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        });
        localStorage.setItem('dory_quiz_history', JSON.stringify(history));
      } catch {
        // History is nice to have; never block the quiz.
      }
      setResults(res);
      setPhase('results');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit quiz');
    } finally {
      setLoading(false);
    }
  }, [session, currentIndex, answers]);

  const handleRestart = useCallback(() => {
    setPhase('intro');
    setSession(null);
    setResults(null);
    setCurrentIndex(0);
    setAnswers([]);
    setError(null);
  }, []);

  const history = (() => {
    try { return JSON.parse(localStorage.getItem('dory_quiz_history') ?? '[]') as { score: number; total: number; date: string }[]; }
    catch { return []; }
  })();

  const avgScore = history.length
    ? Math.round(history.reduce((sum, item) => sum + item.score / item.total, 0) / history.length * 100)
    : null;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
      <main className="min-w-0">
        {error && <div className="mb-4 rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm font-bold text-destructive">{error}</div>}
        {phase === 'intro' && <QuizIntro onStart={handleStart} loading={loading} />}
        {phase === 'playing' && session && (
          <QuizQuestion
            question={session.questions[currentIndex]!}
            questionNumber={currentIndex + 1}
            total={session.questions.length}
            onAnswer={handleAnswer}
          />
        )}
        {phase === 'results' && results && session && (
          <QuizResults results={results} session={session} onRestart={handleRestart} />
        )}
      </main>

      <aside className="space-y-4">
        <div className="app-card p-4">
          <p className="app-label mb-3">Practice stats</p>
          <div className="grid grid-cols-2 gap-3">
            <div className="app-card-muted p-3">
              <BrainCircuit size={17} className="text-[var(--accent)]" />
              <p className="mt-2 text-2xl font-extrabold text-[var(--text-1)]">{history.length}</p>
              <p className="text-sm text-[var(--text-3)]">Sessions</p>
            </div>
            <div className="app-card-muted p-3">
              <Target size={17} className="text-[var(--warn)]" />
              <p className="mt-2 text-2xl font-extrabold text-[var(--text-1)]">{avgScore ?? '-'}</p>
              <p className="text-sm text-[var(--text-3)]">Avg score</p>
            </div>
          </div>
        </div>

        {history.length > 0 && (
          <div className="app-card p-4">
            <p className="app-label mb-3">Recent sessions</p>
            <div className="space-y-2">
              {[...history].reverse().slice(0, 6).map((item, index) => {
                const score = Math.round((item.score / item.total) * 100);
                return (
                  <div key={`${item.date}-${index}`} className="flex items-center justify-between rounded-lg bg-[var(--surface-2)] px-3 py-2 text-sm">
                    <span className="inline-flex items-center gap-2 text-[var(--text-2)]"><CalendarClock size={14} /> {item.date}</span>
                    <span className="font-bold" style={{ color: score >= 70 ? 'var(--good)' : score >= 45 ? 'var(--warn)' : 'var(--danger)' }}>{item.score}/{item.total}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="app-card p-4">
          <p className="app-label mb-3">Review rhythm</p>
          <div className="space-y-2 text-sm text-[var(--text-2)]">
            <p>Start with low-retention chunks.</p>
            <p>Review within 24 hours of first learning.</p>
            <p>Use search after a missed question to inspect the source chunk.</p>
          </div>
        </div>
      </aside>
    </div>
  );
}
