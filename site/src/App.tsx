import { useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { MotionConfig, motion } from 'motion/react'
import { Hero } from '@/components/Hero'
import { Install } from '@/components/Install'
import { Panel, type Part } from '@/components/Panel'
import { NumberTicker } from '@/components/ui/number-ticker'
import { AnimatedSpan, Terminal, TypingAnimation } from '@/components/ui/terminal'
import { cn } from '@/lib/utils'

const REPO = 'https://github.com/aimsotrash/Engram'
// The page's type steps: 13 small, 17 body, 22 lead, `head` for section headings, and the hero's display size.
const head = 'text-[length:var(--step-head)]'
const lead = 'text-[22px] font-medium leading-snug'

/** Rises into place once, as its section enters the screen. */
function Rise({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }} transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay }}>
      {children}
    </motion.div>
  )
}

const code = 'whitespace-pre-wrap break-words rounded-lg p-5 text-[14px] leading-relaxed'

function HowItWorks() {
  return (
    <section id="how" aria-labelledby="how-title" className="px-[var(--margin)] pb-[clamp(96px,12vw,176px)] pt-[clamp(72px,8vw,112px)]">
      <div className="mx-auto max-w-[1280px] min-[1100px]:grid min-[1100px]:grid-cols-[3fr_6fr_3fr] min-[1100px]:gap-12">
        <div className="min-[1100px]:col-start-2">
        <Rise><h2 id="how-title" className={head}>How it works</h2></Rise>
        <ol className="mt-14 space-y-[88px]">
          <li className="max-w-[560px]">
            <Rise><p className={lead}>First, tell your agent something worth keeping.</p></Rise>
            <Rise delay={0.08}><p className={cn(code, 'mt-4 bg-muted')}>&gt; Remember that I take my coffee black, no sugar.</p></Rise>
            <Rise delay={0.16} className="mt-4 min-[700px]:ml-14">
              <pre data-ui className={cn(code, 'bg-[#f2f4f7] dark:bg-[#16181c]')}><code>{'engram.remember("Takes coffee black, no sugar",\n                tags=["preference"])\n{"id": 39, "evicted": []}'}</code></pre>
            </Rise>
          </li>
          <li className="max-w-[560px]">
            <Rise><p className={lead}>Then nothing asks about it for nine days, and it fades.</p></Rise>
            <Rise delay={0.08} className="mt-4">
              <div data-ui className="rounded-lg bg-muted p-5 text-[14px]">
                <div className="flex justify-between"><span className="font-medium">Look ahead</span><span className="tabular-nums text-muted-foreground">in 9 days</span></div>
                <div className="mt-3 h-1.5 rounded-full bg-[#dcdcdc] dark:bg-[#333]"><div className="h-full w-[30%] rounded-full bg-foreground" /></div>
              </div>
            </Rise>
            <Rise delay={0.16} className="mt-4 min-[700px]:ml-14">
              <div data-ui className="grid grid-cols-[1fr_auto] gap-x-3 rounded-lg bg-[#f2f4f7] p-5 text-[14px] dark:bg-[#16181c]">
                <span>Takes coffee black, no sugar</span><span className="text-right tabular-nums">37%</span>
                <span className="flex flex-wrap gap-x-3 text-[13px] text-[#5c6370] dark:text-[#9aa1ad]"><span>#preference</span><span>recalled 0×</span><span>half-life 6.2 d</span></span>
                <span className="flex items-center"><span className="h-1 w-14 overflow-hidden rounded-full bg-[#dde1e8] dark:bg-[#2a2e35]"><span className="block h-full w-[37%] rounded-full bg-[#1d5fbf] dark:bg-[#6f9be8]" /></span></span>
              </div>
            </Rise>
          </li>
          <li>
            <div className="max-w-[560px]">
              <Rise><p className={lead}>A new session asks, and the recall makes it last longer.</p></Rise>
              <Rise delay={0.08}><p className={cn(code, 'mt-4 bg-muted')}>&gt; How do I take my coffee?</p></Rise>
            </div>
            <Rise delay={0.16} className="mt-4 min-[700px]:ml-14">
              <Terminal className="max-h-none w-full max-w-[760px] rounded-lg bg-field p-1 text-field-ink">
                <TypingAnimation duration={22} className="text-[14px] text-field-muted">{'engram.recall("how do I take my coffee", k=5)'}</TypingAnimation>
                <AnimatedSpan className="text-[14px]">39  Takes coffee black, no sugar   strength 0.37   recalled 0×</AnimatedSpan>
                <AnimatedSpan className="text-[14px] text-field-muted">memory 39 is back to 100%; its half-life grows from 6.2 to 8.4 days</AnimatedSpan>
                <TypingAnimation duration={40} className="text-[14px]">Black, no sugar.</TypingAnimation>
              </Terminal>
            </Rise>
          </li>
        </ol>
        </div>
      </div>
    </section>
  )
}

// Margin notes for the panel. On a wide screen each one sits level with the part it explains,
// measured from the panel itself, so the notes follow it when the panel changes.
const NOTES: { part: Part; side: 'left' | 'right'; name: string; text: string }[] = [
  { part: 'remember', side: 'left', name: 'remember', text: 'Stores one fact, preference or decision. When memory is full, the weakest one goes first.' },
  { part: 'recall', side: 'left', name: 'recall', text: 'Finds the memories that fit a question and makes each one last longer. This one has been recalled 4 times.' },
  { part: 'forget', side: 'left', name: 'forget', text: 'Deletes one memory by its id, for good, when your agent calls forget(6). The panel itself only reads.' },
  { part: 'ahead', side: 'right', name: 'Look ahead', text: 'Drag to see how strong each memory will be after more days without a recall.' },
  { part: 'halflife', side: 'right', name: 'Half-life', text: 'Days until a memory falls to half strength: 6.2 when new, and longer after every recall.' },
  { part: 'stats', side: 'right', name: 'memory_stats', text: 'How many memories are kept, the budget and the policy, and their mean strength.' },
]

function Tools() {
  const [focus, setFocus] = useState<Part | null>(null)
  const [layout, setLayout] = useState<{ tops: Partial<Record<Part, number>>; height: number }>({ tops: {}, height: 0 })
  const panelRef = useRef<HTMLDivElement>(null)
  const headingRef = useRef<HTMLDivElement>(null)
  const noteRefs = useRef<Partial<Record<Part, HTMLDivElement | null>>>({})

  useLayoutEffect(() => {
    const root = panelRef.current
    if (!root) return
    // Each note goes level with its part of the panel, or just below the note above it if they would touch.
    let height = 0
    const measure = () => {
      const base = root.getBoundingClientRect().top
      const tops: Partial<Record<Part, number>> = {}
      for (const side of ['left', 'right'] as const) {
        let floor = side === 'left' ? (headingRef.current?.offsetHeight ?? 0) + 24 : 0
        for (const n of NOTES.filter((n) => n.side === side)) {
          const target = root.querySelector(`[data-part="${n.part}"]`)  // hidden under the Fading tab, say
          const want = target ? Math.round(target.getBoundingClientRect().top - base) : floor
          const top = Math.max(want, floor)
          tops[n.part] = top
          floor = top + (noteRefs.current[n.part]?.offsetHeight ?? 0) + 20
        }
        height = Math.max(height, floor)
      }
      setLayout({ tops, height })
    }
    const run = () => { height = root.offsetHeight; measure() }
    run()
    const resized = new ResizeObserver(run)
    const changed = new MutationObserver(run)  // rows re-sort as the look-ahead moves
    for (const el of [root, headingRef.current, ...Object.values(noteRefs.current)]) if (el) resized.observe(el)
    changed.observe(root, { childList: true, subtree: true })
    return () => { resized.disconnect(); changed.disconnect() }
  }, [])

  const note = (n: (typeof NOTES)[number]) => (
    <div key={n.part} ref={(el) => { noteRefs.current[n.part] = el }} onMouseEnter={() => setFocus(n.part)} onMouseLeave={() => setFocus(null)}
         className={cn('max-w-[26ch] min-[1100px]:absolute', n.side === 'left' ? 'min-[1100px]:right-0 min-[1100px]:text-right' : 'min-[1100px]:left-0')}
         style={{ top: layout.tops[n.part] }}>
      <h3 className={cn('text-[22px] font-medium leading-tight tracking-normal transition-colors', focus === n.part && 'text-primary')}>
        {n.name}
      </h3>
      <p className="mt-1 text-[17px] leading-snug text-muted-foreground">{n.text}</p>
    </div>
  )
  // The columns take the panel's height on a wide screen, so the notes have room beside it.
  const tall = { '--panel-h': `${layout.height}px` } as CSSProperties
  return (
    <section id="tools" aria-labelledby="tools-title" className="px-[var(--margin)] pb-[clamp(96px,12vw,176px)]">
      <div className="mx-auto grid max-w-[1280px] gap-10 min-[1100px]:grid-cols-[1fr_392px_1fr] min-[1100px]:gap-14">
        <div className="relative min-[1100px]:min-h-[var(--panel-h)]" style={tall}>
          <div ref={headingRef}><Rise><h2 id="tools-title" className={cn(head, 'min-[1100px]:text-right')}>Four tools and a panel</h2></Rise></div>
          <div className="mt-8 grid gap-6 min-[640px]:grid-cols-2 min-[1100px]:mt-0 min-[1100px]:block">{NOTES.filter((n) => n.side === 'left').map(note)}</div>
        </div>
        <Rise delay={0.08} className="flex justify-center">
          <div ref={panelRef} className="w-full max-w-[392px]"><Panel focus={focus} /></div>
        </Rise>
        <div className="relative grid gap-6 min-[640px]:grid-cols-2 min-[1100px]:block min-[1100px]:min-h-[var(--panel-h)]" style={tall}>
          {NOTES.filter((n) => n.side === 'right').map(note)}
        </div>
      </div>
      <p className="mx-auto mt-12 max-w-[1280px] text-center text-[17px] text-muted-foreground">
        The panel runs on your machine with <code className="text-foreground">python -m engram_mcp.panel</code> and never goes online.
      </p>
    </section>
  )
}

const RESULTS: { value: number; sign?: string; unit?: string; text: string }[] = [
  { value: 58.5, unit: '%', text: 'of LongMemEval questions have all their evidence in the top 10 results when nothing is forgotten.' },
  { value: 36.8, unit: '%', text: 'is the best any forgetting rule reaches on LongMemEval with room for half the history.' },
  { value: 3.9, sign: '+', text: 'points more of the evidence kept than LRU, by strengthening on recall, at half the history.' },
  { value: 14.0, sign: '+', text: 'points more questions with every answer session in the top 10 than with LRU, by strengthening on recall, at a quarter of the history.' },
  { value: 17.2, sign: '−', text: 'points on LongMemEval at a quarter or half of the history: when a fact changes, FSRS-style spacing finds the newest version less often than LRU.' },
  { value: 26.8, unit: '%', text: "is LoCoMo's best at half the history, from keeping the newest. Engram does not beat it there." },
]

function Results() {
  return (
    <section id="results" aria-labelledby="results-title" className="px-[var(--margin)] pb-[clamp(72px,8vw,120px)]">
      <div className="mx-auto grid max-w-[1280px] grid-cols-1 gap-1.5 min-[640px]:grid-cols-2 min-[900px]:grid-cols-4 min-[900px]:gap-2">
        <Rise className="flex min-h-[160px] flex-col justify-between bg-blue p-6 text-blue-ink min-[640px]:col-span-2 min-[900px]:min-h-[232px]">
          <h2 id="results-title" className={head}>Measured, losses included</h2>
          <p className="mt-6 max-w-[46ch] text-[17px] leading-snug">
            Two public benchmarks. Settings were picked on a fixed dev split before any test question was scored.
          </p>
        </Rise>
        {RESULTS.map((r, i) => (
          <Rise key={r.text} delay={0.05 * (i + 1)} className="flex flex-col bg-muted p-6 min-[900px]:min-h-[232px]">
            <p className={cn(head, 'font-bold leading-none tracking-[-0.02em] tabular-nums')}>
              {r.sign}<NumberTicker value={r.value} decimalPlaces={1} className="tracking-[-0.02em] text-foreground dark:text-foreground" />{r.unit}
            </p>
            <p className="mt-4 text-[17px] leading-snug">{r.text}</p>
          </Rise>
        ))}
      </div>
      <p className="mx-auto mt-8 max-w-[1280px] text-[17px] leading-snug text-muted-foreground">
        The comparisons with LRU were chosen after the LongMemEval results came in; on LoCoMo, where the main one was
        chosen before the run, it held with smaller gains. Read <a className="text-primary underline" href={`${REPO}/blob/main/bench/RESULTS.md`}>every LongMemEval result</a>{' '}
        and <a className="text-primary underline" href={`${REPO}/blob/main/bench/RESULTS-locomo.md`}>every LoCoMo result</a>, with the losses.
      </p>
    </section>
  )
}

function InstallSection() {
  return (
    <section id="install" aria-labelledby="install-heading" className="bg-blue px-[var(--margin)] py-16 text-blue-ink">
      <div className="mx-auto grid min-h-[78svh] max-w-[1280px] items-center gap-12 min-[1000px]:grid-cols-[5fr_1fr_5fr]">
        <div className="min-w-0 self-end pb-2">
          <h2 id="install-heading" className={head}>
            <span className="block">Give your agent</span><span className="block">a memory</span>
          </h2>
          <p className="mt-6 max-w-[42ch] text-[17px] leading-relaxed">
            Three commands from a fresh clone. The memories stay in one SQLite file on your machine, and only what a
            recall returns enters your agent's context.
          </p>
        </div>
        <div className="flex min-w-0 justify-center min-[1000px]:col-start-3"><Install /></div>
      </div>
    </section>
  )
}

function Origin() {
  const caption = 'mt-3 text-[13px] leading-snug text-muted-foreground'
  const plate = 'w-full bg-white mix-blend-multiply dark:mix-blend-normal dark:invert'
  return (
    <section id="origin" aria-labelledby="origin-title" className="px-[var(--margin)] py-[clamp(96px,12vw,176px)]">
      <div className="mx-auto grid max-w-[1280px] gap-12 min-[1100px]:grid-cols-[3fr_6fr_3fr]">
        <Rise className="order-2 min-[1100px]:order-none min-[1100px]:pt-24">
          <figure>
            <img src="/pictures/ebbinghaus-fig2.png" width={1243} height={853} loading="lazy" className={plate}
                 alt="A hand-drawn line chart from 1885: learning time in seconds rises steeply from the first list to the second, then levels off." />
            <figcaption className={caption}>
              Hermann Ebbinghaus, Über das Gedächtnis, 1885, Fig. 2: the seconds he needed to learn each of eight lists of
              13 nonsense syllables in a row, averaged over 92 tests.
            </figcaption>
          </figure>
        </Rise>
        <div className="max-w-[560px]">
          <Rise><h2 id="origin-title" className={head}>Where it came from</h2></Rise>
          <Rise delay={0.08} className="mt-10">
            <div aria-hidden="true" className="flex size-11 items-center justify-center rounded-full bg-foreground text-[14px] font-semibold text-background">NP</div>
            <div className="mt-7 space-y-5 text-[17px] leading-[1.55]">
              <p>
                Engram began as a notes app. It gave every note a strength that decayed along Ebbinghaus's forgetting
                curve, so search could put first what you were about to forget.
              </p>
              <p>
                In October I pointed the same engine at AI agents. An agent that runs for weeks collects more memories than it
                can use, so I asked a plain question: should it forget? In Engram, a memory fades unless it is recalled, and
                every recall makes it last longer.
              </p>
              <p>
                Then I measured it against keeping everything, keeping the newest and keeping the most recently used, on two
                public benchmarks. Keeping everything wins when you can afford it. Under a budget, strengthening on recall
                helps a little, and strengthening too hard hides facts that change.
              </p>
              <p>
                MemoryBank tried an Ebbinghaus curve on LLM memory in 2023. What is new here is the measured comparison, losses
                included, and the code, the benchmark and every result are open.
              </p>
            </div>
            <p className="mt-8 text-[22px] font-medium">Nikhil Pawar</p>
            <p className="text-[13px] text-muted-foreground">Graduate student, Northeastern University, Seattle</p>
          </Rise>
        </div>
        <Rise delay={0.12} className="order-3 min-[1100px]:order-none min-[1100px]:pt-[340px]">
          <figure>
            <img src="/pictures/cajal-hippocampus.png" width={1268} height={687} loading="lazy" className={plate}
                 alt="Santiago Ramón y Cajal's ink drawing of the hippocampus, its regions labeled CA1, CA3, DG, Sub and EC, with a small circuit diagram." />
            <figcaption className={caption}>
              Santiago Ramón y Cajal's drawing of the hippocampus, where new memories form, 1911. The labels and the circuit
              were added later.
            </figcaption>
          </figure>
        </Rise>
      </div>
      <Rise className="mx-auto mt-[clamp(72px,10vw,140px)] max-w-[1280px]">
        <figure>
          <div className="overflow-hidden">
            <img src="/pictures/cajal-laboratory.jpg" width={1920} height={1395} loading="lazy"
                 className="drift aspect-[16/7] w-full object-cover object-[50%_40%] grayscale"
                 alt="An old photograph: Cajal, white-bearded, points while lecturing to a row of men in lab coats beside a bench of glassware." />
          </div>
          <figcaption className={caption}>Santiago Ramón y Cajal teaching in his laboratory.</figcaption>
        </figure>
      </Rise>
    </section>
  )
}

function Footer() {
  return (
    <footer className="px-[var(--margin)] pb-[30px] pt-[20svh] text-[13px]">
      <p className="mx-auto mb-6 max-w-[1280px] leading-snug text-muted-foreground">
        Pictures, all public domain via Wikimedia Commons:{' '}
        <a className="underline" href="https://commons.wikimedia.org/wiki/File:%C3%9Cber_das_Ged%C3%A4chtnis._Untersuchungen_zur_experimentellen_Psychologie,_Fig_2.png">Über das Gedächtnis, Fig. 2</a> by Hermann Ebbinghaus;{' '}
        <a className="underline" href="https://commons.wikimedia.org/wiki/File:CajalHippocampus_(modified).png">CajalHippocampus (modified)</a>, after Santiago Ramón y Cajal;{' '}
        <a className="underline" href="https://commons.wikimedia.org/wiki/File:Santiago_Ram%C3%B3n_y_Cajal_dando_c%C3%A1tedra_en_su_laboratorio.jpg">Santiago Ramón y Cajal dando cátedra en su laboratorio</a>.
      </p>
      <div className="mx-auto grid max-w-[1280px] gap-2 text-muted-foreground min-[800px]:grid-cols-[1fr_auto_1fr] min-[800px]:items-baseline">
        <span>Engram, memory for AI agents</span>
        <span className="flex flex-wrap gap-x-6 gap-y-1 text-foreground">
          <a className="hover:underline" href={REPO}>GitHub</a>
          <a className="hover:underline" href="#results">Results</a>
          <a className="hover:underline" href="#install">Install</a>
          <a className="hover:underline" href={`${REPO}/blob/main/LICENSE`}>MIT License</a>
        </span>
        <span className="min-[800px]:text-right">2026</span>
      </div>
    </footer>
  )
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <Hero />
      <main>
        <HowItWorks />
        <Tools />
        <Results />
        <InstallSection />
        <Origin />
      </main>
      <Footer />
    </MotionConfig>
  )
}
