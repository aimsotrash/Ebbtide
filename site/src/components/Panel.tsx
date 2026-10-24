import { useMemo, useState } from 'react'
import { Slider } from '@/components/ui/slider'
import { cn } from '@/lib/utils'
import { days, halfLifeDays, pct, stability, strength } from '@/lib/memory'

// A coding agent's memories about this project, as the panel shows them. Stability follows the
// count rule (S = 1 + 0.5 ln(1 + recalls)); strength is computed from it, never typed in.
const MEMORIES = [
  { id: 52, text: 'Keeping everything wins when storage allows', tags: ['results'], added: 0, recalls: 0, last: null },
  { id: 12, text: 'Ask before pushing to main: main deploys the frontend', tags: ['rule'], added: 21, recalls: 4, last: 1 },
  { id: 47, text: 'The showcase poster is due November 23', tags: ['deadline'], added: 5, recalls: 1, last: 1 },
  { id: 30, text: 'The tests stub the embedder, so CI skips torch', tags: ['project'], added: 12, recalls: 3, last: 2 },
  { id: 49, text: 'The showcase is at 225 Terry Ave N, Seattle', tags: ['event'], added: 3, recalls: 0, last: null },
  { id: 25, text: 'The MCP server keeps its memories in SQLite', tags: ['project'], added: 14, recalls: 2, last: 6 },
  { id: 38, text: 'Commit messages are plain, with no co-author lines', tags: ['preference'], added: 9, recalls: 1, last: 8 },
  { id: 39, text: 'Takes coffee black, no sugar', tags: ['preference'], added: 9, recalls: 0, last: null },
  { id: 6, text: 'Use uv for Python virtual environments', tags: ['tooling'], added: 26, recalls: 0, last: null },
]
export const BUDGET = 1000
const NEWEST = 52, MOST_RECALLED = 12 // the rows the remember and recall notes point at

export type Part = 'remember' | 'recall' | 'forget' | 'stats' | 'halflife' | 'ahead'

export function Panel({ focus }: { focus?: Part | null }) {
  const [ahead, setAhead] = useState(0)
  const [tab, setTab] = useState<'all' | 'fading'>('all')
  const rows = useMemo(
    () =>
      MEMORIES.map((m) => {
        const s = stability(m.recalls)
        const r = strength((m.last ?? m.added) + ahead, s)
        return { ...m, r, halfLife: halfLifeDays(s) }
      }).sort((a, b) => b.r - a.r),
    [ahead],
  )
  const fading = rows.filter((m) => m.r < 0.5)
  const shown = tab === 'all' ? rows : fading
  const mean = rows.reduce((sum, m) => sum + m.r, 0) / rows.length
  const weakest = rows[rows.length - 1].id
  const lit = (part: Part) => focus === part && 'ring-2 ring-primary ring-offset-2 ring-offset-[#f2f4f7] dark:ring-offset-[#16181c]'

  return (
    <div data-ui className="w-[min(100%,392px)] rounded-lg bg-[#f2f4f7] p-4 text-[14px] leading-snug text-[#111] dark:bg-[#16181c] dark:text-[#ededed]">
      <div className="flex items-center gap-2">
        <svg viewBox="0 0 32 32" className="size-6 shrink-0" aria-hidden="true">
          <rect width="32" height="32" rx="7" fill="currentColor" />
          <path d="M7 8.5C11.5 8.5 13.5 21 25.5 22.5" fill="none" className="stroke-[#f2f4f7] dark:stroke-[#16181c]" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
        <span className="text-[17px] font-semibold">Memories</span>
        <span className="ml-auto text-[13px] text-[#5c6370] tabular-nums dark:text-[#9aa1ad]">
          {rows.length} kept of {BUDGET.toLocaleString('en-US')}
        </span>
      </div>

      <div data-part="ahead" className={cn('mt-4 rounded-md bg-white p-3 dark:bg-[#1f2227]', lit('ahead'))}>
        <div className="flex items-baseline justify-between text-[13px]">
          <label htmlFor="panel-ahead" className="font-medium">Look ahead</label>
          <span className="text-[#5c6370] tabular-nums dark:text-[#9aa1ad]">{ahead ? `in ${ahead} days` : 'today'}</span>
        </div>
        <Slider id="panel-ahead" className="mt-3" min={0} max={30} step={1} value={[ahead]}
                onValueChange={([v]) => setAhead(v)} aria-label="Look ahead, in days" aria-valuetext={ahead ? `in ${ahead} days` : 'today'} />
      </div>

      <div role="group" aria-label="Which memories" className={"mt-4 flex gap-5 border-b border-[#dde1e8] text-[13px] dark:border-[#2a2e35]" /* taste-skill-ignore: underline tabs sit on a 1px rule */}>
        {(['all', 'fading'] as const).map((t) => (
          <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}
                  className={cn('-mb-px border-b-2 pb-2 font-medium transition-colors',
                    tab === t ? 'border-[#111] text-[#111] dark:border-[#ededed] dark:text-[#ededed]' : 'border-transparent text-[#5c6370] hover:text-[#111] dark:text-[#9aa1ad] dark:hover:text-[#ededed]')}>
            {t === 'all' ? `All ${rows.length}` : `Fading ${fading.length}`}
          </button>
        ))}
      </div>

      <ul className="mt-1">
        {shown.map((m) => (
          <li key={m.id} data-part={m.id === NEWEST ? 'remember' : m.id === MOST_RECALLED ? 'recall' : undefined}
              className={cn('group grid grid-cols-[1fr_auto] gap-x-3 rounded-md px-1 py-2.5',
                m.id === NEWEST && lit('remember'), m.id === MOST_RECALLED && lit('recall'))}>
            <span className="line-clamp-2">{m.text}</span>
            <span className="text-right tabular-nums">{pct(m.r)}</span>
            <span className="flex flex-wrap gap-x-3 text-[13px] text-[#5c6370] dark:text-[#9aa1ad]">
              <span data-part={m.id === weakest ? 'forget' : undefined} className={cn('rounded-sm', m.id === weakest && lit('forget'))}>id {m.id}</span>
              <span>{m.tags.map((t) => `#${t}`).join(' ')}</span>
              <span>recalled {m.recalls}×</span>
              <span data-part={m.id === 30 ? 'halflife' : undefined} className={cn('rounded-sm', m.id === 30 && lit('halflife'))}>half-life {days(m.halfLife)}</span>
            </span>
            <span className="flex items-center justify-end">
              <span aria-hidden="true" className="h-1 w-14 overflow-hidden rounded-full bg-[#dde1e8] dark:bg-[#2a2e35]">
                <span className="block h-full rounded-full bg-[#1d5fbf] transition-[width] duration-300 dark:bg-[#6f9be8]" style={{ width: pct(m.r) }} />
              </span>
            </span>
          </li>
        ))}
      </ul>

      <div data-part="stats" className={cn('mt-2 flex flex-wrap gap-x-4 gap-y-1 rounded-sm px-1 pt-3 text-[13px] text-[#5c6370] tabular-nums dark:text-[#9aa1ad]', lit('stats'))}>
        <span>budget {BUDGET.toLocaleString('en-US')}</span>
        <span>policy engram-count</span>
        <span>mean strength {pct(mean)}</span>
      </div>
    </div>
  )
}
