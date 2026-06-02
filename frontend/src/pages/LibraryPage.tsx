import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  BookOpen, Loader2, FolderPlus, FolderOpen, Check, Trash2,
  Filter, ArrowDownAZ, Lock, Search, NotebookPen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getAllChunks, bulkDeleteChunks, getFolders, moveChunkToFolder } from '@/lib/api';
import { NoteDetailPanel, type PanelChunk } from '@/components/notes/NoteDetailPanel';
import type { BackendChunk, Category } from '@/lib/types';
import { categoryColors, retentionToColor, retentionToLabel } from '@/styles/theme';
import { formatRetentionPct } from '@/lib/utils';

const ENC_PREFIX = 'ENC:';
const ALL_CATEGORIES: Category[] = ['technical', 'personal', 'reference', 'general'];

interface LibraryChunk extends BackendChunk {
  folder?: string | null;
}

function toPanel(c: LibraryChunk): PanelChunk {
  return {
    id: c.chunk_id,
    source_file: c.source_file,
    category: c.category,
    retention: c.retention,
    access_count: c.access_count,
    last_accessed: c.last_accessed,
    folder: c.folder,
    content: c.content,
  };
}

function baseName(path: string) {
  return path.split(/[\\/]/).pop() ?? path;
}

function normalizedCategory(category?: string | null): Category {
  const cat = (category ?? '').toLowerCase();
  if (cat.includes('technical') || cat.includes('code') || cat.includes('algorithm') || cat.includes('data')) return 'technical';
  if (cat.includes('personal')) return 'personal';
  if (cat.includes('reference')) return 'reference';
  return 'general';
}

export function LibraryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [chunks, setChunks] = useState<LibraryChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [folders, setFolders] = useState<string[]>([]);
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [filterCat, setFilterCat] = useState<Category | 'all'>('all');
  const [sortBy, setSortBy] = useState<'retention' | 'recent' | 'access'>('retention');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [activeChunkId, setActiveChunkId] = useState<string | null>(searchParams.get('chunk'));
  const [newFolderName, setNewFolderName] = useState('');
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [chunkRes, folderRes] = await Promise.all([getAllChunks(), getFolders().catch(() => [])]);
      setChunks(chunkRes.chunks.map((c) => ({ ...c, folder: (c as LibraryChunk).folder ?? null })));
      setFolders(folderRes);
    } catch {
      setChunks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // Sync URL ?chunk=<id> ↔ activeChunkId so deep-links from the dashboard work
  // and the URL updates when the user clicks a chunk in this page.
  useEffect(() => {
    const fromUrl = searchParams.get('chunk');
    if (fromUrl && fromUrl !== activeChunkId) setActiveChunkId(fromUrl);
    // Intentionally keyed only on the URL → state direction.
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const fromUrl = searchParams.get('chunk');
    if (activeChunkId && activeChunkId !== fromUrl) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('chunk', activeChunkId);
        return next;
      }, { replace: true });
    } else if (!activeChunkId && fromUrl) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.delete('chunk');
        return next;
      }, { replace: true });
    }
    // Intentionally keyed only on the state → URL direction.
  }, [activeChunkId]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeChunk = chunks.find((c) => c.chunk_id === activeChunkId) ?? null;

  const visible = useMemo(() => {
    return chunks
      .filter((chunk) => {
        if (activeFolder !== null && (chunk.folder ?? null) !== activeFolder) return false;
        if (filterCat !== 'all' && normalizedCategory(chunk.category) !== filterCat) return false;
        if (searchTerm.trim()) {
          const q = searchTerm.toLowerCase();
          return chunk.content.toLowerCase().includes(q) || chunk.source_file.toLowerCase().includes(q) || (chunk.folder ?? '').toLowerCase().includes(q);
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'retention') return (a.retention ?? 0) - (b.retention ?? 0);
        if (sortBy === 'recent') return new Date(b.last_accessed_iso).getTime() - new Date(a.last_accessed_iso).getTime();
        return b.access_count - a.access_count;
      });
  }, [chunks, activeFolder, filterCat, searchTerm, sortBy]);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelected((prev) => prev.size === visible.length ? new Set() : new Set(visible.map((c) => c.chunk_id)));
  }

  async function doBulkDelete() {
    const ids = [...selected];
    await bulkDeleteChunks(ids);
    setChunks((prev) => prev.filter((c) => !ids.includes(c.chunk_id)));
    setSelected(new Set());
    setConfirmBulkDelete(false);
    if (activeChunkId && ids.includes(activeChunkId)) setActiveChunkId(null);
    getFolders().then(setFolders).catch(() => {});
  }

  async function moveSelected(folder: string | null) {
    const ids = [...selected];
    await Promise.all(ids.map((id) => moveChunkToFolder(id, folder)));
    setChunks((prev) => prev.map((c) => selected.has(c.chunk_id) ? { ...c, folder } : c));
    setSelected(new Set());
    getFolders().then(setFolders).catch(() => {});
  }

  function createFolder() {
    const name = newFolderName.trim();
    if (!name) return;
    setFolders((prev) => Array.from(new Set([...prev, name])).sort());
    setNewFolderName('');
  }

  return (
    <div className="grid min-h-[calc(100vh-132px)] gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <section className="app-card flex min-h-[620px] flex-col overflow-hidden">
        <div className="border-b border-[var(--border)] p-4">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-extrabold text-[var(--text-1)]">Library</h1>
              <p className="mt-1 text-sm text-[var(--text-3)]">Browse, edit, and write notes. {chunks.length} chunk{chunks.length === 1 ? '' : 's'}.</p>
            </div>
            <Link to="/notes" className="btn-primary text-sm shrink-0">
              <NotebookPen size={14} /> New note
            </Link>
          </div>

          <div className="relative mb-3">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-3)]" />
            <input
              className="corp-input pl-9"
              placeholder="Filter files, folders, or content..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="mb-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => setActiveFolder(null)} className={cn('btn-ghost', activeFolder === null && 'bg-[var(--accent-soft)] text-[var(--accent)]')}>
              All folders
            </button>
            {folders.map((folder) => (
              <button
                key={folder}
                type="button"
                onClick={() => setActiveFolder(folder)}
                className={cn('btn-ghost', activeFolder === folder && 'bg-[var(--accent-soft)] text-[var(--accent)]')}
              >
                <FolderOpen size={14} /> {folder}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-xs font-bold text-[var(--text-3)]"><Filter size={13} /> Category</span>
            <button type="button" onClick={() => setFilterCat('all')} className={cn('tag', filterCat === 'all' && 'border-[var(--accent-border)] bg-[var(--accent-soft)] text-[var(--accent)]')}>All</button>
            {ALL_CATEGORIES.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setFilterCat(cat)}
                className="tag capitalize"
                style={filterCat === cat ? { color: categoryColors[cat], borderColor: `${categoryColors[cat]}55`, background: `${categoryColors[cat]}16` } : undefined}
              >
                {cat}
              </button>
            ))}
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)} className="corp-input ml-auto w-auto min-w-[150px]">
              <option value="retention">Fading first</option>
              <option value="recent">Recently accessed</option>
              <option value="access">Most reviewed</option>
            </select>
          </div>
        </div>

        <div className="border-b border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
          {selected.size > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-auto text-sm font-bold text-[var(--text-1)]">{selected.size} selected</span>
              <button type="button" className="btn-secondary" onClick={() => moveSelected(null)}>
                <FolderOpen size={14} /> No folder
              </button>
              {folders.slice(0, 3).map((folder) => (
                <button key={folder} type="button" className="btn-secondary" onClick={() => moveSelected(folder)}>
                  <FolderOpen size={14} /> {folder}
                </button>
              ))}
              <button type="button" className="btn-secondary text-[var(--danger)]" onClick={() => setConfirmBulkDelete(true)}>
                <Trash2 size={14} /> Delete
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button type="button" onClick={selectAll} className="btn-ghost">
                <Check size={14} /> Select visible
              </button>
              <div className="ml-auto flex items-center gap-2">
                <input
                  className="corp-input h-9 w-36"
                  placeholder="New folder"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') createFolder(); }}
                />
                <button type="button" className="btn-secondary h-9" onClick={createFolder}>
                  <FolderPlus size={14} />
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-16"><Loader2 size={22} className="animate-spin text-[var(--accent)]" /></div>
          ) : visible.length === 0 ? (
            <div className="p-10 text-center text-[var(--text-3)]">
              <BookOpen size={30} className="mx-auto mb-3" />
              <p className="font-bold text-[var(--text-1)]">{chunks.length === 0 ? 'No chunks yet' : 'No chunks in this view'}</p>
              <p className="mt-1 text-sm">Import files or clear filters to populate the library.</p>
            </div>
          ) : visible.map((chunk) => {
            const retention = chunk.retention ?? 0.5;
            const color = retentionToColor(retention);
            const category = normalizedCategory(chunk.category);
            const isActive = activeChunkId === chunk.chunk_id;
            const isSelected = selected.has(chunk.chunk_id);
            const isEncrypted = chunk.content.startsWith(ENC_PREFIX) || chunk.content === '[Encrypted]';
            return (
              <button
                key={chunk.chunk_id}
                type="button"
                onClick={() => setActiveChunkId(chunk.chunk_id)}
                className={cn(
                  'block w-full border-b border-[var(--border)] p-4 text-left transition',
                  isActive ? 'bg-[var(--accent-soft)]' : 'hover:bg-[var(--surface-2)]'
                )}
              >
                <div className="flex items-start gap-3">
                  <span
                    onClick={(e) => { e.stopPropagation(); toggleSelect(chunk.chunk_id); }}
                    className={cn(
                      'mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded border',
                      isSelected ? 'border-[var(--accent)] bg-[var(--accent)] text-white' : 'border-[var(--border-strong)] bg-[var(--surface)]'
                    )}
                  >
                    {isSelected && <Check size={11} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="truncate text-sm font-bold text-[var(--text-1)]">{baseName(chunk.source_file)}</span>
                      {isEncrypted && <Lock size={13} className="shrink-0 text-[var(--warn)]" />}
                      <span className="ml-auto text-xs font-bold" style={{ color }}>{formatRetentionPct(retention)}</span>
                    </div>
                    <p className="line-clamp-2 text-sm leading-relaxed text-[var(--text-2)]">
                      {isEncrypted ? 'Encrypted note' : chunk.content}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span className="tag capitalize" style={{ color: categoryColors[category], borderColor: `${categoryColors[category]}44`, background: `${categoryColors[category]}14` }}>
                        {category}
                      </span>
                      <span className="tag" style={{ color, borderColor: `${color}44`, background: `${color}14` }}>
                        {retentionToLabel(retention)}
                      </span>
                      {chunk.folder && <span className="tag"><FolderOpen size={12} /> {chunk.folder}</span>}
                      <span className="text-xs text-[var(--text-3)]">{chunk.last_accessed}</span>
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <section className="app-card min-h-[620px] overflow-hidden">
        {activeChunk ? (
          <NoteDetailPanel
            chunk={toPanel(activeChunk)}
            folders={folders}
            onDelete={(id) => {
              setChunks((prev) => prev.filter((c) => c.chunk_id !== id));
              setActiveChunkId(null);
              getFolders().then(setFolders).catch(() => {});
            }}
            onContentUpdate={(id, content) => {
              setChunks((prev) => prev.map((c) => c.chunk_id === id ? { ...c, content: content.slice(0, 300) } : c));
            }}
            onFolderChange={(id, folder) => {
              setChunks((prev) => prev.map((c) => c.chunk_id === id ? { ...c, folder } : c));
              getFolders().then(setFolders).catch(() => {});
            }}
          />
        ) : (
          <div className="flex h-full min-h-[620px] flex-col items-center justify-center gap-3 px-8 text-center">
            <ArrowDownAZ size={34} className="text-[var(--text-4)]" />
            <p className="font-bold text-[var(--text-1)]">Select a chunk</p>
            <p className="max-w-sm text-sm text-[var(--text-3)]">Edit content, move folders, run AI transforms, or encrypt sensitive notes.</p>
          </div>
        )}
      </section>

      {confirmBulkDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4">
          <div className="app-card w-full max-w-sm p-5 shadow-[var(--shadow)]">
            <h3 className="font-bold text-[var(--text-1)]">Delete {selected.size} chunks?</h3>
            <p className="mt-2 text-sm text-[var(--text-3)]">This permanently removes them from your knowledge base.</p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setConfirmBulkDelete(false)}>Cancel</button>
              <button type="button" className="btn-primary bg-[var(--danger)] hover:bg-[var(--danger)]" onClick={doBulkDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
