import { useState, useEffect, useRef, useCallback } from 'react';
import { RotateCcw, SkipForward, Timer, TrendingUp, Flame, Clock, Play, Pause } from 'lucide-react';

type Mode = 'work' | 'short' | 'long';

const DURATIONS: Record<Mode, number> = { work: 25 * 60, short: 5 * 60, long: 15 * 60 };
const LABELS: Record<Mode, string> = { work: 'Focus', short: 'Short break', long: 'Long break' };
const COLORS: Record<Mode, string> = { work: 'var(--accent)', short: 'var(--good)', long: 'var(--warn)' };
const WORK_MIN = 25;
const SESSION_KEY = 'dory_pomodoro_v1';
const TIMER_KEY = 'dory_pomodoro_timer';

interface StoredSession {
  mode: Mode;
  at: string;
  date: string;
}

interface PomodoroStore {
  sessions: StoredSession[];
  totalCycles: number;
}

interface TimerState {
  mode: Mode;
  pausedRemaining: number;
  startedAt: number | null;
}

function todayKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function loadStore(): PomodoroStore {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) ?? 'null') ?? { sessions: [], totalCycles: 0 }; }
  catch { return { sessions: [], totalCycles: 0 }; }
}

function saveStore(store: PomodoroStore) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(store));
}

function loadTimerState(): TimerState {
  try { return JSON.parse(localStorage.getItem(TIMER_KEY) ?? 'null') ?? { mode: 'work', pausedRemaining: DURATIONS.work, startedAt: null }; }
  catch { return { mode: 'work', pausedRemaining: DURATIONS.work, startedAt: null }; }
}

function saveTimerState(state: TimerState) {
  localStorage.setItem(TIMER_KEY, JSON.stringify(state));
}

function computeRemaining(state: TimerState) {
  if (state.startedAt === null) return state.pausedRemaining;
  const elapsed = Math.floor((Date.now() - state.startedAt) / 1000);
  return Math.max(0, state.pausedRemaining - elapsed);
}

function fmt(seconds: number) {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

function lastNDays(n: number) {
  const days: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
  }
  return days;
}

export function PomodoroPage() {
  const [timerState, setTimerStateRaw] = useState<TimerState>(loadTimerState);
  const [remaining, setRemaining] = useState(() => computeRemaining(loadTimerState()));
  const [store, setStore] = useState<PomodoroStore>(loadStore);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mode = timerState.mode;
  const running = timerState.startedAt !== null;
  const total = DURATIONS[mode];
  const progress = (total - remaining) / total;
  const color = COLORS[mode];

  function setTimerState(next: TimerState) {
    setTimerStateRaw(next);
    saveTimerState(next);
  }

  const finish = useCallback(() => {
    const finishedMode = mode;
    const entry: StoredSession = { mode: finishedMode, at: new Date().toISOString(), date: todayKey() };
    setStore((prev) => {
      const nextStore = {
        sessions: [...prev.sessions, entry],
        totalCycles: finishedMode === 'work' ? prev.totalCycles + 1 : prev.totalCycles,
      };
      saveStore(nextStore);
      const nextMode: Mode = finishedMode === 'work'
        ? (nextStore.totalCycles % 4 === 0 && nextStore.totalCycles > 0 ? 'long' : 'short')
        : 'work';
      const nextTimer = { mode: nextMode, pausedRemaining: DURATIONS[nextMode], startedAt: null };
      setTimerState(nextTimer);
      setRemaining(DURATIONS[nextMode]);
      return nextStore;
    });
  }, [mode]);

  useEffect(() => {
    if (!running) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          finish();
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [running, finish]);

  useEffect(() => {
    // Restore a persisted timer once on mount; `finish` is stable enough here.
    const state = loadTimerState();
    if (state.startedAt !== null) {
      const nextRemaining = computeRemaining(state);
      if (nextRemaining <= 0) finish();
      else setRemaining(nextRemaining);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function startTimer() {
    setTimerState({ mode, pausedRemaining: remaining, startedAt: Date.now() });
  }

  function pauseTimer() {
    setTimerState({ mode, pausedRemaining: remaining, startedAt: null });
  }

  function reset() {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setTimerState({ mode, pausedRemaining: DURATIONS[mode], startedAt: null });
    setRemaining(DURATIONS[mode]);
  }

  function switchMode(nextMode: Mode) {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setTimerState({ mode: nextMode, pausedRemaining: DURATIONS[nextMode], startedAt: null });
    setRemaining(DURATIONS[nextMode]);
  }

  const today = todayKey();
  const todaySessions = store.sessions.filter((session) => session.date === today);
  const todayWorkMin = todaySessions.filter((session) => session.mode === 'work').length * WORK_MIN;
  const allWorkSessions = store.sessions.filter((session) => session.mode === 'work').length;
  const allBreaks = store.sessions.filter((session) => session.mode !== 'work').length;
  const weekDays = lastNDays(7);
  const weekCounts = weekDays.map((day) => store.sessions.filter((session) => session.date === day && session.mode === 'work').length);
  const weekMax = Math.max(...weekCounts, 1);

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <div className="app-card p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
              <Timer size={22} />
            </span>
            <div>
              <h1 className="text-2xl font-extrabold text-[var(--text-1)]">Focus timer</h1>
              <p className="text-sm text-[var(--text-3)]">A persistent timer for deep work around review sessions.</p>
            </div>
          </div>
          <span className="tag"><Flame size={14} /> {todayWorkMin}m today</span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section className="app-card p-6">
          <div className="mb-6 grid grid-cols-3 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-1">
            {(['work', 'short', 'long'] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                className={mode === m ? 'btn-primary' : 'btn-ghost'}
                style={mode === m ? { background: COLORS[m] } : undefined}
              >
                {LABELS[m]}
              </button>
            ))}
          </div>

          <div className="flex flex-col items-center">
            <div className="relative h-72 w-72">
              <svg viewBox="0 0 280 280" className="h-full w-full -rotate-90">
                <circle cx="140" cy="140" r="112" fill="none" stroke="#e4d9c8" strokeWidth="16" />
                <circle
                  cx="140"
                  cy="140"
                  r="112"
                  fill="none"
                  stroke={color}
                  strokeWidth="16"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 112}`}
                  strokeDashoffset={`${(1 - progress) * 2 * Math.PI * 112}`}
                  style={{ transition: 'stroke-dashoffset 1s linear' }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <p className="text-6xl font-extrabold tabular-nums" style={{ color }}>{fmt(remaining)}</p>
                <p className="mt-2 text-sm font-bold text-[var(--text-3)]">{LABELS[mode]}</p>
                {running && <span className="tag mt-3" style={{ color, borderColor: 'currentColor' }}>Running</span>}
              </div>
            </div>

            <div className="mt-6 flex items-center gap-3">
              <button type="button" onClick={reset} className="btn-secondary h-11 w-11 p-0" title="Reset"><RotateCcw size={17} /></button>
              <button type="button" onClick={running ? pauseTimer : startTimer} className="btn-primary min-w-36" style={{ background: color }}>
                {running ? <Pause size={17} /> : <Play size={17} />}
                {running ? 'Pause' : 'Start'}
              </button>
              <button type="button" onClick={finish} className="btn-secondary h-11 w-11 p-0" title="Skip"><SkipForward size={17} /></button>
            </div>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="app-card p-4">
              <TrendingUp size={18} className="text-[var(--accent)]" />
              <p className="mt-3 text-3xl font-extrabold text-[var(--text-1)]">{allWorkSessions}</p>
              <p className="text-sm text-[var(--text-3)]">Work sessions</p>
            </div>
            <div className="app-card p-4">
              <Clock size={18} className="text-[var(--warn)]" />
              <p className="mt-3 text-3xl font-extrabold text-[var(--text-1)]">{allBreaks}</p>
              <p className="text-sm text-[var(--text-3)]">Breaks</p>
            </div>
          </div>

          <div className="app-card p-4">
            <p className="app-label mb-4">This week</p>
            <div className="flex h-28 items-end gap-2">
              {weekCounts.map((count, index) => {
                const height = count === 0 ? 6 : Math.max(12, Math.round((count / weekMax) * 88));
                const label = new Date(`${weekDays[index]}T12:00:00`).toLocaleDateString([], { weekday: 'short' }).slice(0, 2);
                return (
                  <div key={weekDays[index]} className="flex flex-1 flex-col items-center gap-2">
                    <div className="w-full rounded-t bg-[var(--accent)]" style={{ height, opacity: count ? 0.9 : 0.18 }} />
                    <span className="text-xs font-bold text-[var(--text-3)]">{label}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="app-card p-4">
            <p className="app-label mb-3">Recent sessions</p>
            {store.sessions.length === 0 ? (
              <p className="text-sm text-[var(--text-3)]">No focus sessions logged yet.</p>
            ) : (
              <div className="space-y-2">
                {[...store.sessions].reverse().slice(0, 8).map((session, index) => (
                  <div key={`${session.at}-${index}`} className="flex items-center justify-between rounded-lg bg-[var(--surface-2)] px-3 py-2 text-sm">
                    <span className="font-bold text-[var(--text-2)]">{LABELS[session.mode]}</span>
                    <span className="text-[var(--text-3)]">{new Date(session.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
