import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SearchBar } from '@/components/search/SearchBar';
import { CardSkeleton } from '@/components/ui/LoadingSkeleton';
import { NoteDetailPanel, type PanelChunk } from '@/components/notes/NoteDetailPanel';
import { search } from '@/lib/api';
import type { SearchResult } from '@/lib/types';
import { Search, Star, FileText, Activity } from 'lucide-react';
import { retentionToColor, categoryColors, retentionToLabel } from '@/styles/theme';
import { formatRetentionPct, cn } from '@/lib/utils';
import { sanitizeHtml } from '@/lib/sanitize';
import type { Category } from '@/lib/types';

function baseName(path: string) {
  return path.split(/[\\/]/).pop() ?? path;
}

function toPanel(chunk: SearchResult['chunk']): PanelChunk {
  return {
    id: chunk.id,
    source_file: (chunk as unknown as { source_name?: string }).source_name ?? chunk.id,
    category: chunk.category,
    retention: chunk.retention,
    access_count: chunk.access_count,
    last_accessed: chunk.last_accessed,
    content: chunk.content,
  };
}

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [results, setResults] = useState<SearchResult[]>([]);
  const [query, setQuery] = useState(searchParams.get('q') ?? '');
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeResult, setActiveResult] = useState<SearchResult | null>(null);

  const handleSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setSearched(false);
      setActiveResult(null);
      setQuery('');
      return;
    }
    setQuery(q);
    setSearchParams({ q });
    setLoading(true);
    setError(null);
    setActiveResult(null);
    try {
      const res = await search(q);
      setResults(res.results);
      setSearched(true);
      setActiveResult(res.results[0] ?? null);
    } catch (e) {
      // Clear stale results so the error banner isn't shown alongside the
      // previous query's hits (UI_REVIEW U-3).
      setResults([]);
      setSearched(true);
      setActiveResult(null);
      setError(e instanceof Error ? e.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }, [setSearchParams]);

  useEffect(() => {
    // Run once on mount to honor a ?q= deep-link; intentionally not re-run.
    const q = searchParams.get('q');
    if (q && !searched) void handleSearch(q);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Layout: single full-width column when no result is active; split layout (results | detail) once the user clicks something.
  const hasDetail = activeResult !== null;

  return (
    <div className={`grid min-h-[calc(100vh-132px)] gap-4 ${hasDetail ? 'xl:grid-cols-[460px_minmax(0,1fr)]' : 'mx-auto max-w-3xl'}`}>
      <section className="app-card flex min-h-[620px] flex-col overflow-hidden">
        <div className="border-b border-[var(--border)] p-4">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-extrabold text-[var(--text-1)]">Discovery search</h1>
              <p className="mt-1 text-sm text-[var(--text-3)]">Hybrid search over your indexed memory chunks.</p>
            </div>
            {searched && (
              <span className="tag">
                <Activity size={13} /> {results.length} result{results.length === 1 ? '' : 's'}
              </span>
            )}
          </div>
          <SearchBar onSearch={handleSearch} loading={loading} initialValue={query} placeholder="Search concepts, files, or phrases..." />
        </div>

        <div className="flex-1 overflow-y-auto">
          {error && <p className="m-4 rounded-lg bg-red-50 p-3 text-sm text-[var(--danger)]">{error}</p>}

          {loading && (
            <div className="space-y-3 p-4">
              {[1, 2, 3, 4].map((i) => <CardSkeleton key={i} />)}
            </div>
          )}

          {!loading && results.map((result) => {
            const retention = result.chunk.retention ?? 0.5;
            const color = retentionToColor(retention);
            const category = (result.chunk.category?.toLowerCase() as Category) ?? 'general';
            const catColor = categoryColors[category] ?? categoryColors.general;
            const isActive = activeResult?.chunk.id === result.chunk.id;
            const sourceName = (result.chunk as unknown as { source_name?: string }).source_name ?? result.chunk.id;

            return (
              <button
                key={result.chunk.id}
                type="button"
                onClick={() => setActiveResult(result)}
                className={cn(
                  'block w-full border-b border-[var(--border)] p-4 text-left transition',
                  isActive ? 'bg-[var(--accent-soft)]' : 'hover:bg-[var(--surface-2)]'
                )}
              >
                <div className="mb-2 flex items-center gap-2">
                  <FileText size={14} className="shrink-0 text-[var(--text-3)]" />
                  <span className="min-w-0 flex-1 truncate text-xs font-bold text-[var(--text-3)]">{baseName(sourceName)}</span>
                  {result.score !== undefined && (
                    <span className="inline-flex items-center gap-1 text-xs font-bold text-[var(--accent)]">
                      <Star size={12} /> {Math.round(result.score * 100)}%
                    </span>
                  )}
                </div>
                <p className="line-clamp-3 text-sm leading-relaxed text-[var(--text-2)]">
                  {result.highlight ? <span dangerouslySetInnerHTML={{ __html: sanitizeHtml(result.highlight) }} /> : result.chunk.content}
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="tag capitalize" style={{ color: catColor, borderColor: `${catColor}44`, background: `${catColor}14` }}>
                    {result.chunk.category ?? 'general'}
                  </span>
                  <span className="tag" style={{ color, borderColor: `${color}44`, background: `${color}14` }}>
                    {retentionToLabel(retention)} {formatRetentionPct(retention)}
                  </span>
                </div>
              </button>
            );
          })}

          {!loading && searched && results.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 p-10 text-center text-[var(--text-3)]">
              <Search size={30} />
              <p className="font-bold text-[var(--text-1)]">No matching chunks</p>
              <p className="text-sm">Try a broader concept or import more notes.</p>
            </div>
          )}

          {!loading && !searched && (
            <div className="flex flex-col items-center justify-center gap-3 p-10 text-center text-[var(--text-3)]">
              <Search size={30} />
              <p className="font-bold text-[var(--text-1)]">Start with a concept</p>
              <p className="max-w-xs text-sm">Search understands both exact text and related ideas when the backend is running.</p>
            </div>
          )}
        </div>
      </section>

      {hasDetail && (
        <section className="app-card min-h-[620px] overflow-hidden">
          <NoteDetailPanel
            chunk={toPanel(activeResult.chunk)}
            onDelete={(id) => {
              setResults((prev) => prev.filter((r) => r.chunk.id !== id));
              setActiveResult(null);
            }}
            onContentUpdate={(id, content) => {
              setResults((prev) => prev.map((r) => r.chunk.id === id ? { ...r, chunk: { ...r.chunk, content } } : r));
            }}
          />
        </section>
      )}
    </div>
  );
}
