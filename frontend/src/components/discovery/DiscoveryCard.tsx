import { X, Sparkles, Clock, FileText, ArrowRight, Zap } from 'lucide-react';
import { retentionToColor, retentionToLabel } from '@/styles/theme';
import { formatRetentionPct, formatRelativeTime } from '@/lib/utils';
import type { DiscoveryResponse } from '@/lib/types';
import { Link } from 'react-router-dom';

interface DiscoveryCardProps {
  discovery: Extract<DiscoveryResponse, { has_discovery: true }>;
  onDismiss: () => void;
}

export function DiscoveryCard({ discovery, onDismiss }: DiscoveryCardProps) {
  const { chunk, reason } = discovery;
  const retention = chunk.retention ?? 0.5;
  const color = retentionToColor(retention);
  const label = retentionToLabel(retention);

  return (
    <div className="app-card animate-slide-in-right border-l-4 p-4" style={{ borderLeftColor: color }}>
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
          <Sparkles size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-sm font-bold text-[var(--text-1)]">Dory found a fading memory</span>
            <span className="tag" style={{ color, borderColor: `color-mix(in oklab, ${color} 27%, transparent)`, background: `color-mix(in oklab, ${color} 9%, transparent)` }}>
              {label} {formatRetentionPct(retention)}
            </span>
          </div>
          <p className="line-clamp-2 text-sm leading-relaxed text-[var(--text-2)]">{chunk.content}</p>
          <p className="mt-2 text-xs text-[var(--text-3)]">{reason}</p>
          <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-[var(--text-3)]">
            <span className="inline-flex items-center gap-1.5">
              <Clock size={13} /> {formatRelativeTime(chunk.last_accessed)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <FileText size={13} /> {chunk.source_name}
            </span>
            <Link
              to={`/search?q=${encodeURIComponent(chunk.content.slice(0, 50))}`}
              className="ml-auto inline-flex items-center gap-1.5 font-bold text-[var(--accent)] hover:text-[var(--accent-hover)]"
            >
              <Zap size={13} /> Review now <ArrowRight size={13} />
            </Link>
          </div>
        </div>
        <button type="button" onClick={onDismiss} className="btn-ghost h-8 w-8 shrink-0 p-0" title="Dismiss">
          <X size={15} />
        </button>
      </div>
    </div>
  );
}
