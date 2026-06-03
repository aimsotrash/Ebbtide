// Retention thresholds MUST mirror the backend's single source of truth
// (intelligence/memory/ebbinghaus.py: STRONG=0.8, FADING=0.5, WEAK=0.2). Keeping
// these in sync avoids the dashboard re-bucketing chunks differently from the
// server (UI_REVIEW D-1).
export const STRONG_THRESHOLD = 0.8;
export const FADING_THRESHOLD = 0.5;
export const WEAK_THRESHOLD = 0.2;

// Retention/data-viz colors are expressed in oklch and mirror the semantic
// tokens in styles.css: strong=good, fading=warn, weak=orange, critical=destructive.
export function retentionToColor(retention: number): string {
  if (retention >= STRONG_THRESHOLD) return 'oklch(0.60 0.13 150)';
  if (retention >= FADING_THRESHOLD) return 'oklch(0.70 0.15 70)';
  if (retention >= WEAK_THRESHOLD) return 'oklch(0.65 0.17 45)';
  return 'oklch(0.577 0.245 27)';
}

export function retentionToGlow(retention: number): string {
  if (retention >= STRONG_THRESHOLD) return 'oklch(0.60 0.13 150 / 0.2)';
  if (retention >= FADING_THRESHOLD) return 'oklch(0.70 0.15 70 / 0.2)';
  if (retention >= WEAK_THRESHOLD) return 'oklch(0.65 0.17 45 / 0.2)';
  return 'oklch(0.577 0.245 27 / 0.2)';
}

export function retentionToLabel(retention: number): string {
  if (retention >= STRONG_THRESHOLD) return 'Strong';
  if (retention >= FADING_THRESHOLD) return 'Fading';
  if (retention >= WEAK_THRESHOLD) return 'Weak';
  return 'Critical';
}

// Keys are lowercased category names. Covers the backend taxonomy
// (intelligence/llm/categorization.py CATEGORIES) plus legacy frontend labels.
// `general` is the fallback used when a category isn't listed.
export const categoryColors: Record<string, string> = {
  'computer science': 'oklch(0.55 0.12 260)',
  'ai/ml': 'oklch(0.58 0.18 290)',
  'system design': 'oklch(0.60 0.08 190)',
  mathematics: 'oklch(0.62 0.15 350)',
  design: 'oklch(0.70 0.15 70)',
  productivity: 'oklch(0.60 0.13 150)',
  research: 'oklch(0.55 0.12 260)',
  personal: 'oklch(0.55 0.08 185)',
  other: 'oklch(0.60 0.01 70)',
  // legacy / fallback keys
  technical: 'oklch(0.55 0.12 260)',
  reference: 'oklch(0.70 0.15 70)',
  general: 'oklch(0.58 0.18 290)',
};
