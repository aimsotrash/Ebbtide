// The forgetting curve the page demonstrates, copied from intelligence/memory/agent.py so the
// numbers here are the real store's: R = e^(-t / (S * 216 h)), S starts at 1.

export const SCALE_HOURS = 216 // 9 days: how long a new memory takes to fall to 1/e

// FSRS-6 default weights, as the "spaced" rule uses them (see agent.py).
const W4 = 6.4133, W5 = 0.8334, W8 = 1.8722, W9 = 0.1666, W10 = 0.796
const D = W4 - Math.exp(2 * W5) + 1
const SPACED_GAIN = Math.exp(W8) * (11 - D)

export type Rule = 'count' | 'spaced'

export const strength = (daysSince: number, stability: number) =>
  Math.exp((-daysSince * 24) / (stability * SCALE_HOURS))

/** The count rule's stability after `recalls` recalls, as ebbinghaus.stability computes it. */
export const stability = (recalls: number) => 1 + 0.5 * Math.log1p(recalls)

export const halfLifeDays = (stability: number) => (Math.LN2 * stability * SCALE_HOURS) / 24

/** Stability after one more recall, made when the memory's strength was `r`. */
export function strengthen(rule: Rule, s: number, recalls: number, r: number) {
  if (rule === 'count') return stability(recalls + 1)
  return s * (1 + SPACED_GAIN * s ** -W9 * Math.expm1(W10 * (1 - r)))
}

export const pct = (r: number) => `${Math.round(100 * r)}%`
export const days = (d: number) => `${d.toFixed(1)} d`
