// Retention thresholds MUST mirror the backend's single source of truth
// (intelligence/memory/ebbinghaus.py: STRONG=0.8, FADING=0.5, WEAK=0.2). Keeping
// these in sync avoids the dashboard re-bucketing chunks differently from the
// server (UI_REVIEW D-1).
export const STRONG_THRESHOLD = 0.8;
export const FADING_THRESHOLD = 0.5;
export const WEAK_THRESHOLD = 0.2;

export function retentionToColor(retention: number): string {
  if (retention >= STRONG_THRESHOLD) return '#3a8d54';
  if (retention >= FADING_THRESHOLD) return '#c97917';
  if (retention >= WEAK_THRESHOLD) return '#d66a2f';
  return '#c94433';
}

export function retentionToGlow(retention: number): string {
  if (retention >= STRONG_THRESHOLD) return 'rgba(58, 141, 84, 0.2)';
  if (retention >= FADING_THRESHOLD) return 'rgba(201, 121, 23, 0.2)';
  if (retention >= WEAK_THRESHOLD) return 'rgba(214, 106, 47, 0.2)';
  return 'rgba(201, 68, 51, 0.2)';
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
  'computer science': '#466fb0',
  'ai/ml': '#6d5bd0',
  'system design': '#2f8f83',
  mathematics: '#b0568f',
  design: '#c97917',
  productivity: '#3a8d54',
  research: '#466fb0',
  personal: '#147a72',
  other: '#888276',
  // legacy / fallback keys
  technical: '#466fb0',
  reference: '#c97917',
  general: '#6d5bd0',
};
