import { useState } from 'react'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/utils'
import { days, halfLifeDays, pct, strength, strengthen, type Rule } from '@/lib/memory'

// The headline is a memory: its weight and ink follow its strength on the real curve, a recall
// snaps it back, and the switch trades the count rule for FSRS-style spacing.
export function Hero() {
  const [daysSince, setDaysSince] = useState(0)
  const [stability, setStability] = useState(1)
  const [recalls, setRecalls] = useState(0)
  const [rule, setRule] = useState<Rule>('count')
  const r = strength(daysSince, stability)

  const recall = () => {
    setStability(strengthen(rule, stability, recalls, r))
    setRecalls(recalls + 1)
    setDaysSince(0)
  }
  const switchRule = (spaced: boolean) => {
    setRule(spaced ? 'spaced' : 'count') // a new rule starts the memory over, so the two compare
    setStability(1)
    setRecalls(0)
    setDaysSince(0)
  }

  const chip = 'rounded-lg bg-field-raised px-4 py-3 text-[14px] leading-snug text-field-ink'
  const daysChip = (
    <div data-ui className={cn(chip, 'w-[min(100%,300px)] min-[1100px]:-rotate-3')}>
      <div className="flex items-baseline justify-between gap-4">
        <span id="hero-days-label" className="font-medium">Days without a recall</span>
        <span className="tabular-nums text-field-muted">{daysSince} d</span>
      </div>
      <Slider id="hero-days" className="mt-3 [&_[data-slot=slider-range]]:bg-field-ink [&_[data-slot=slider-thumb]]:border-field-ink [&_[data-slot=slider-track]]:bg-[#3a3a3a]"
              aria-labelledby="hero-days-label" aria-valuetext={`${daysSince} days, strength ${pct(r)}`}
              min={0} max={60} step={1} value={[daysSince]} onValueChange={([v]) => setDaysSince(v)} />
      <p className="mt-2 tabular-nums text-field-muted">strength {pct(r)}</p>
    </div>
  )
  const recallChip = (
    <div data-ui className={cn(chip, 'flex w-[min(100%,300px)] items-center gap-4 min-[1100px]:rotate-2')}>
      <button onClick={recall}
              className="rounded-md bg-field-ink px-3.5 py-2 font-medium text-field transition-transform hover:scale-[1.03] active:scale-[0.97]">
        Recall it
      </button>
      <span className="tabular-nums text-field-muted" aria-live="polite">recalled {recalls}×<br />half-life {days(halfLifeDays(stability))}</span>
    </div>
  )
  const ruleChip = (
    <div data-ui className={cn(chip, 'flex w-[min(100%,300px)] items-center justify-between gap-4 min-[1100px]:-rotate-2')}>
      <div>
        <span id="hero-rule-label" className="block font-medium">Spaced rule</span>
        <span id="hero-rule-state" className="text-field-muted">{rule === 'count' ? 'off: the count rule' : 'on: FSRS-style spacing'}</span>
      </div>
      <Switch id="hero-rule" checked={rule === 'spaced'} onCheckedChange={switchRule}
              aria-labelledby="hero-rule-label" aria-describedby="hero-rule-state"
              className="data-[state=checked]:bg-field-ink data-[state=unchecked]:bg-[#3a3a3a] [&[data-state=checked]_[data-slot=switch-thumb]]:bg-field" />
    </div>
  )

  return (
    <header id="top" className="relative flex min-h-svh flex-col bg-field px-[var(--margin)] text-field-ink [--ring:#8aa4ff]">
      <nav className="mx-auto flex w-full max-w-[1280px] items-center justify-between pt-7" aria-label="Main">
        <a href="#top" className="text-[14px] font-semibold">Engram</a>
        <div className="flex items-center gap-6 text-[14px]">
          <a href="#how" className="hidden hover:underline sm:inline">How it works</a>
          <a href="#results" className="hidden hover:underline sm:inline">Results</a>
          <a href="https://github.com/aimsotrash/Engram" className="hidden hover:underline sm:inline">GitHub</a>
          <a href="#install" className="inline-flex h-11 items-center bg-blue px-5 font-medium text-blue-ink transition-transform hover:scale-[1.03] active:scale-[0.97]">
            Install
          </a>
        </div>
      </nav>

      <div className="flex flex-1 flex-col items-center justify-center pb-[12svh] pt-16">
        <div className="relative w-full max-w-[1280px]">
          <div className="mb-6 flex justify-center min-[1100px]:absolute min-[1100px]:-top-28 min-[1100px]:left-[19%] min-[1100px]:mb-0">
            {daysChip}
          </div>
          <h1 className="text-center text-[11.5vw] leading-[1.0] min-[1100px]:text-[clamp(96px,9vw,150px)]"
              style={{ fontWeight: Math.round(200 + 500 * r), opacity: 0.42 + 0.58 * r, transition: 'font-weight 250ms, opacity 250ms' }}>
            <span className="block overflow-hidden pb-[0.25em] -mb-[0.19em]"><span className="rise">Agent memory</span></span>
            <span className="block overflow-hidden pb-[0.25em] -mb-[0.19em]"><span className="rise [animation-delay:110ms]">that fades</span></span>
          </h1>
          <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row sm:justify-center min-[1100px]:mt-0 min-[1100px]:contents">
            <div className="min-[1100px]:absolute min-[1100px]:bottom-[6%] min-[1100px]:left-[1%]">{recallChip}</div>
            <div className="min-[1100px]:absolute min-[1100px]:-bottom-24 min-[1100px]:right-[2%]">{ruleChip}</div>
          </div>
        </div>
        <p className="appear mt-[72px] max-w-[40ch] text-center text-[17px] leading-relaxed text-field-ink min-[1100px]:mt-[120px]">
          An MCP server that gives AI agents long-term memory. Memories fade unless they are recalled,
          and each recall makes one last longer.
        </p>
      </div>
    </header>
  )
}
