import { useState, useEffect, useMemo } from 'react';
import { getAllChunks } from '@/lib/api';
import type { BackendChunk } from '@/lib/types';
import { ChevronLeft, ChevronRight, CalendarDays, X, BookOpen, AlertTriangle } from 'lucide-react';
import { retentionToColor } from '@/styles/theme';
import { formatRetentionPct } from '@/lib/utils';

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const DAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

function predictForgetDate(chunk: BackendChunk): Date {
  const now = Date.now();
  const lastMs = new Date(chunk.last_accessed_iso).getTime();
  const elapsedHours = Math.max((now - lastMs) / 3_600_000, 0.01);
  const r = Math.max(Math.min(chunk.retention, 0.9999), 0.0001);
  const stability = elapsedHours / -Math.log(r);
  return new Date(lastMs + Math.log(5) * stability * 3_600_000);
}

function dateKey(d: Date) {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function daysUntil(d: Date) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  return Math.floor((target - today) / 86_400_000);
}

function urgencyColor(days: number) {
  if (days < 0) return 'var(--danger)';
  if (days < 2) return 'oklch(0.65 0.17 45)';
  if (days < 7) return 'var(--warn)';
  if (days < 30) return 'var(--good)';
  return 'var(--accent)';
}

function truncate(text: string, max: number) {
  return text.length <= max ? text : `${text.slice(0, max)}...`;
}

export function CalendarPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [selected, setSelected] = useState<string | null>(dateKey(now));
  const [chunks, setChunks] = useState<BackendChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [openChunk, setOpenChunk] = useState<BackendChunk | null>(null);

  useEffect(() => {
    getAllChunks().then((r) => setChunks(r.chunks)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const forgetMap = useMemo(() => {
    const map: Record<string, BackendChunk[]> = {};
    chunks.forEach((chunk) => {
      const key = dateKey(predictForgetDate(chunk));
      map[key] = [...(map[key] ?? []), chunk];
    });
    return map;
  }, [chunks]);

  const selectedChunks = selected ? (forgetMap[selected] ?? []) : [];
  const cells: (number | null)[] = [
    ...Array(getFirstDayOfWeek(year, month)).fill(null),
    ...Array.from({ length: getDaysInMonth(year, month) }, (_, i) => i + 1),
  ];

  const upcoming = useMemo(() => chunks
    .map((chunk) => ({ chunk, date: predictForgetDate(chunk) }))
    .filter(({ date }) => {
      const days = daysUntil(date);
      return days >= 0 && days <= 30;
    })
    .sort((a, b) => a.date.getTime() - b.date.getTime())
    .slice(0, 16), [chunks]);

  function prev() {
    if (month === 0) {
      setMonth(11);
      setYear((y) => y - 1);
    } else setMonth((m) => m - 1);
  }

  function next() {
    if (month === 11) {
      setMonth(0);
      setYear((y) => y + 1);
    } else setMonth((m) => m + 1);
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
      <section className="space-y-4">
        <div className="app-card p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-2xl font-extrabold text-[var(--text-1)]">Review calendar</h1>
              <p className="mt-1 text-sm text-[var(--text-3)]">Predicted dates when chunks cross the critical retention threshold.</p>
            </div>
            {loading && <span className="tag">Loading chunks...</span>}
          </div>
        </div>

        <div className="app-card p-5">
          <div className="mb-5 flex items-center justify-between">
            <button type="button" onClick={prev} className="btn-secondary h-10 w-10 p-0" title="Previous month"><ChevronLeft size={17} /></button>
            <div className="text-center">
              <p className="text-xl font-extrabold text-[var(--text-1)]">{MONTHS[month]}</p>
              <p className="text-sm text-[var(--text-3)]">{year}</p>
            </div>
            <button type="button" onClick={next} className="btn-secondary h-10 w-10 p-0" title="Next month"><ChevronRight size={17} /></button>
          </div>

          <div className="grid grid-cols-7 gap-2">
            {DAYS.map((day) => <div key={day} className="app-label py-1 text-center">{day}</div>)}
            {cells.map((day, index) => {
              if (!day) return <div key={`empty-${index}`} />;
              const key = `${year}-${month}-${day}`;
              const date = new Date(year, month, day);
              const events = forgetMap[key] ?? [];
              const isToday = key === dateKey(now);
              const isSelected = key === selected;
              const color = urgencyColor(daysUntil(date));
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSelected(isSelected ? null : key)}
                  className="min-h-20 rounded-lg border p-2 text-left transition hover:bg-[var(--surface-2)]"
                  style={{
                    borderColor: isSelected ? 'var(--accent-border)' : events.length ? `color-mix(in oklab, ${color} 33%, transparent)` : 'var(--border)',
                    background: isSelected ? 'var(--accent-soft)' : isToday ? 'oklch(var(--lavender) / 0.08)' : 'var(--surface)',
                  }}
                >
                  <span className="text-sm font-bold text-[var(--text-1)]">{day}</span>
                  {events.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {events.slice(0, 4).map((event) => (
                        <span key={event.chunk_id} className="h-2 w-2 rounded-full" style={{ background: retentionToColor(event.retention) }} />
                      ))}
                      {events.length > 4 && <span className="text-xs font-bold text-[var(--text-3)]">+{events.length - 4}</span>}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {selected && (
          <div className="app-card p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="app-section-title">
                {MONTHS[month]} {Number(selected.split('-')[2])}, {year}
              </h2>
              <button type="button" onClick={() => setSelected(null)} className="btn-ghost h-8 w-8 p-0"><X size={15} /></button>
            </div>
            {selectedChunks.length === 0 ? (
              <p className="rounded-lg bg-[var(--surface-2)] p-4 text-sm text-[var(--text-3)]">No chunks predicted to become critical on this day.</p>
            ) : (
              <div className="space-y-2">
                {selectedChunks.map((chunk) => (
                  <button key={chunk.chunk_id} type="button" onClick={() => setOpenChunk(chunk)} className="flex w-full items-start gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 text-left hover:bg-[var(--surface)]">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[var(--warn)]" />
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 text-sm leading-relaxed text-[var(--text-2)]">{truncate(chunk.content, 160)}</p>
                      <p className="mt-1 text-xs text-[var(--text-3)]">{chunk.source_file.split(/[\\/]/).pop()} / {formatRetentionPct(chunk.retention)}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      <aside className="space-y-4">
        <div className="app-card p-4">
          <h2 className="app-section-title">Next 30 days</h2>
          <p className="mt-1 text-sm text-[var(--text-3)]">Upcoming forgetting events.</p>
          <div className="mt-4 space-y-2">
            {upcoming.length === 0 ? (
              <p className="rounded-lg bg-[var(--surface-2)] p-3 text-sm text-[var(--text-3)]">No upcoming events yet.</p>
            ) : upcoming.map(({ chunk, date }) => {
              const days = daysUntil(date);
              const color = urgencyColor(days);
              return (
                <button key={chunk.chunk_id} type="button" onClick={() => setOpenChunk(chunk)} className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 text-left hover:bg-[var(--surface)]">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs font-bold" style={{ color }}>{days === 0 ? 'today' : days === 1 ? 'tomorrow' : `${days}d`}</span>
                    <span className="text-xs font-bold" style={{ color: retentionToColor(chunk.retention) }}>{formatRetentionPct(chunk.retention)}</span>
                  </div>
                  <p className="line-clamp-2 text-sm text-[var(--text-2)]">{chunk.content}</p>
                </button>
              );
            })}
          </div>
        </div>
      </aside>

      {openChunk && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4" onClick={() => setOpenChunk(null)}>
          <div className="app-card w-full max-w-2xl p-5 shadow-[var(--shadow)]" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <CalendarDays size={17} className="text-[var(--accent)]" />
                <span className="font-bold text-[var(--text-1)]">{openChunk.source_file.split(/[\\/]/).pop()}</span>
              </div>
              <button type="button" onClick={() => setOpenChunk(null)} className="btn-ghost h-8 w-8 p-0"><X size={15} /></button>
            </div>
            <div className="max-h-[50vh] overflow-y-auto rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4 text-sm leading-7 text-[var(--text-2)]">
              {openChunk.content}
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-[var(--text-3)]">
              <span className="tag"><BookOpen size={13} /> {openChunk.access_count} reviews</span>
              <span className="tag" style={{ color: retentionToColor(openChunk.retention), borderColor: `${retentionToColor(openChunk.retention)}44`, background: `${retentionToColor(openChunk.retention)}14` }}>
                {formatRetentionPct(openChunk.retention)} retained
              </span>
              <span>Predicted critical date: {predictForgetDate(openChunk).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
