import { useState, useEffect, useRef, useCallback } from 'react';
import { marked } from 'marked';
import { sanitizeHtml } from '@/lib/sanitize';
import { ingestText, getAllChunks } from '@/lib/api';
import { useNotes } from '@/hooks/useNotes';
import type { BackendChunk } from '@/lib/types';
import { retentionToColor } from '@/styles/theme';
import {
  Plus, Trash2, Search, FileText, Eye, Edit3,
  Download, Upload, Clock, Library, X, Save,
} from 'lucide-react';

const SLASH_COMMANDS = [
  { cmd: '/h1', label: 'Heading 1', icon: 'H1', insert: () => '# ' },
  { cmd: '/h2', label: 'Heading 2', icon: 'H2', insert: () => '## ' },
  { cmd: '/h3', label: 'Heading 3', icon: 'H3', insert: () => '### ' },
  { cmd: '/bullet', label: 'Bullet list', icon: '-', insert: () => '- ' },
  { cmd: '/num', label: 'Numbered', icon: '1.', insert: () => '1. ' },
  { cmd: '/code', label: 'Code block', icon: '<>', insert: () => '```\n\n```\n' },
  { cmd: '/quote', label: 'Blockquote', icon: '"', insert: () => '> ' },
  { cmd: '/divider', label: 'Divider', icon: '--', insert: () => '\n---\n' },
  { cmd: '/bold', label: 'Bold', icon: 'B', insert: () => '**text**' },
  { cmd: '/italic', label: 'Italic', icon: 'I', insert: () => '*text*' },
];

type SaveMode = 'dory' | 'local';

function formatRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function NoteEditorPage() {
  const { notes, createNote, updateNote, deleteNote } = useNotes();
  const [activeId, setActiveId] = useState<string | null>(() => notes[0]?.id ?? null);
  const [search, setSearch] = useState('');
  const [preview, setPreview] = useState(false);
  const [saveMode, setSaveMode] = useState<SaveMode>('dory');
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<{ type: 'ok' | 'err'; msg: string } | null>(null);
  const [slashVisible, setSlashVisible] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');
  const [sidebarTab, setSidebarTab] = useState<'notes' | 'library'>('notes');
  const [importedChunks, setImportedChunks] = useState<BackendChunk[]>([]);
  const [viewChunk, setViewChunk] = useState<BackendChunk | null>(null);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const active = notes.find((note) => note.id === activeId) ?? null;

  useEffect(() => {
    if (!activeId && notes.length > 0) setActiveId(notes[0].id);
  }, [activeId, notes]);

  useEffect(() => {
    if (sidebarTab === 'library' && importedChunks.length === 0) {
      getAllChunks().then((r) => setImportedChunks(r.chunks)).catch(() => {});
    }
  }, [sidebarTab, importedChunks.length]);

  const handleNewNote = useCallback(() => {
    const note = createNote();
    setActiveId(note.id);
    setViewChunk(null);
    window.setTimeout(() => titleRef.current?.focus(), 50);
  }, [createNote]);

  const handleContentChange = useCallback((val: string, textarea: HTMLTextAreaElement) => {
    if (!activeId) return;
    updateNote(activeId, { content: val });
    const cursor = textarea.selectionStart;
    const lineStart = val.lastIndexOf('\n', cursor - 1) + 1;
    const line = val.slice(lineStart, cursor);
    if (line.startsWith('/')) {
      setSlashFilter(line.slice(1).toLowerCase());
      setSlashVisible(true);
    } else {
      setSlashVisible(false);
    }
  }, [activeId, updateNote]);

  const applySlash = useCallback((insert: () => string) => {
    if (!editorRef.current || !active) return;
    const textarea = editorRef.current;
    const val = active.content;
    const cursor = textarea.selectionStart;
    const lineStart = val.lastIndexOf('\n', cursor - 1) + 1;
    const replacement = insert();
    const next = val.slice(0, lineStart) + replacement + val.slice(cursor);
    updateNote(active.id, { content: next });
    setSlashVisible(false);
    window.setTimeout(() => {
      textarea.focus();
      const pos = lineStart + replacement.length;
      textarea.setSelectionRange(pos, pos);
    }, 10);
  }, [active, updateNote]);

  const handleFileImport = useCallback((files: FileList | null) => {
    if (!files?.length) return;
    Array.from(files).forEach(async (file) => {
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (ext === 'md' || ext === 'txt') {
        const text = await file.text();
        const note = createNote();
        updateNote(note.id, { title: file.name.replace(/\.(md|txt)$/i, ''), content: text });
        setActiveId(note.id);
        return;
      }
      if (ext === 'doc' || ext === 'docx') {
        try {
          // @ts-ignore mammoth ships the browser bundle without a TS declaration.
          const mammoth = await import('mammoth/mammoth.browser');
          const buf = await file.arrayBuffer();
          const result = await mammoth.extractRawText({ arrayBuffer: buf });
          const note = createNote();
          updateNote(note.id, { title: file.name.replace(/\.(docx?)$/i, ''), content: result.value });
          setActiveId(note.id);
        } catch {
          setSaveStatus({ type: 'err', msg: `Could not parse ${file.name}` });
        }
      }
    });
  }, [createNote, updateNote]);

  function flash(type: 'ok' | 'err', msg: string) {
    setSaveStatus({ type, msg });
    window.setTimeout(() => setSaveStatus(null), 2500);
  }

  async function handleSave() {
    if (!active) return;
    if (saveMode === 'local') {
      const blob = new Blob([`# ${active.title}\n\n${active.content}`], { type: 'text/markdown' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${(active.title || 'note').replace(/\s+/g, '-').toLowerCase()}.md`;
      a.click();
      flash('ok', 'Downloaded markdown');
      return;
    }
    setSaving(true);
    try {
      await ingestText(`# ${active.title}\n\n${active.content}`, 'note', active.title || 'note');
      flash('ok', 'Indexed in Dory');
    } catch (e) {
      flash('err', e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  const filteredNotes = notes.filter((note) =>
    !search || note.title.toLowerCase().includes(search.toLowerCase()) || note.content.toLowerCase().includes(search.toLowerCase())
  );
  const filteredSlash = SLASH_COMMANDS.filter((command) =>
    command.cmd.slice(1).startsWith(slashFilter) || command.label.toLowerCase().startsWith(slashFilter)
  );
  const wordCount = (active?.content ?? '').split(/\s+/).filter(Boolean).length;
  const renderedHtml = sanitizeHtml(marked.parse(active?.content ?? '') as string);

  return (
    <div className="grid min-h-[calc(100vh-132px)] gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="app-card flex min-h-[620px] flex-col overflow-hidden">
        <div className="border-b border-[var(--border)] p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div className="grid grid-cols-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-1 text-sm font-bold">
              <button type="button" onClick={() => setSidebarTab('notes')} className={sidebarTab === 'notes' ? 'btn-primary h-8' : 'btn-ghost h-8'}>
                <FileText size={14} /> Notes
              </button>
              <button type="button" onClick={() => setSidebarTab('library')} className={sidebarTab === 'library' ? 'btn-primary h-8' : 'btn-ghost h-8'}>
                <Library size={14} /> Library
              </button>
            </div>
            {sidebarTab === 'notes' && <button type="button" onClick={handleNewNote} className="btn-secondary h-9 w-9 p-0" title="New note"><Plus size={15} /></button>}
          </div>
          <div className="relative">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-3)]" />
            <input className="corp-input pl-9" placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {sidebarTab === 'notes' ? (
            filteredNotes.length === 0 ? (
              <div className="p-8 text-center text-[var(--text-3)]">
                <FileText size={28} className="mx-auto mb-3" />
                <p className="font-bold text-[var(--text-1)]">No notes yet</p>
                <button type="button" onClick={handleNewNote} className="btn-primary mt-4"><Plus size={15} /> New note</button>
              </div>
            ) : filteredNotes.map((note) => (
              <button
                key={note.id}
                type="button"
                onClick={() => { setActiveId(note.id); setViewChunk(null); }}
                className={`block w-full border-b border-[var(--border)] p-3 text-left transition hover:bg-[var(--surface-2)] ${note.id === activeId && !viewChunk ? 'bg-[var(--accent-soft)]' : ''}`}
              >
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-bold text-[var(--text-1)]">{note.title || 'Untitled'}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-[var(--text-3)]">{note.content || 'Empty note'}</p>
                    <p className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--text-4)]"><Clock size={12} /> {formatRelative(note.updated_at)}</p>
                  </div>
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      const next = notes.find((n) => n.id !== note.id)?.id ?? null;
                      if (activeId === note.id) setActiveId(next);
                      deleteNote(note.id);
                    }}
                    className="btn-ghost h-8 w-8 p-0 text-[var(--danger)] opacity-80"
                  >
                    <Trash2 size={14} />
                  </span>
                </div>
              </button>
            ))
          ) : (
            importedChunks.length === 0 ? (
              <div className="p-8 text-center text-[var(--text-3)]">
                <Library size={28} className="mx-auto mb-3" />
                <p className="font-bold text-[var(--text-1)]">No imported chunks</p>
              </div>
            ) : importedChunks
              .filter((chunk) => !search || chunk.content.toLowerCase().includes(search.toLowerCase()) || chunk.source_file.toLowerCase().includes(search.toLowerCase()))
              .map((chunk) => {
                const color = retentionToColor(chunk.retention ?? 0.5);
                const isActive = viewChunk?.chunk_id === chunk.chunk_id;
                return (
                  <button
                    key={chunk.chunk_id}
                    type="button"
                    onClick={() => setViewChunk(chunk)}
                    className={`block w-full border-b border-[var(--border)] p-3 text-left transition hover:bg-[var(--surface-2)] ${isActive ? 'bg-[var(--accent-soft)]' : ''}`}
                  >
                    <p className="truncate font-bold text-[var(--text-1)]">{chunk.source_file.split(/[\\/]/).pop()}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-[var(--text-3)]">{chunk.content}</p>
                    <p className="mt-2 text-xs font-bold" style={{ color }}>{Math.round((chunk.retention ?? 0.5) * 100)}% retained</p>
                  </button>
                );
              })
          )}
        </div>

        <div className="border-t border-[var(--border)] p-4">
          <label className="btn-secondary w-full">
            <Upload size={15} />
            Import .md / .txt / .docx
            <input type="file" accept=".md,.txt,.doc,.docx" multiple className="hidden" onChange={(e) => handleFileImport(e.target.files)} />
          </label>
        </div>
      </aside>

      <section className="app-card flex min-h-[620px] flex-col overflow-hidden">
        {viewChunk ? (
          <>
            <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface-2)] px-5 py-3">
              <div className="min-w-0">
                <p className="truncate font-bold text-[var(--text-1)]">{viewChunk.source_file.split(/[\\/]/).pop()}</p>
                <p className="text-sm text-[var(--text-3)]">{Math.round((viewChunk.retention ?? 0.5) * 100)}% retained / {viewChunk.access_count} reviews</p>
              </div>
              <button type="button" onClick={() => setViewChunk(null)} className="btn-ghost h-8 w-8 p-0"><X size={15} /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-8">
              <div className="mx-auto max-w-3xl whitespace-pre-wrap text-base leading-8 text-[var(--text-2)]">{viewChunk.content}</div>
            </div>
          </>
        ) : active ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--surface-2)] px-5 py-3">
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => setPreview(false)} className={!preview ? 'btn-primary h-9' : 'btn-secondary h-9'}><Edit3 size={14} /> Write</button>
                <button type="button" onClick={() => setPreview(true)} className={preview ? 'btn-primary h-9' : 'btn-secondary h-9'}><Eye size={14} /> Preview</button>
                {wordCount > 0 && <span className="tag">{wordCount} words</span>}
              </div>

              <div className="flex items-center gap-2">
                {saveStatus && <span className={`tag ${saveStatus.type === 'ok' ? 'badge-strong' : 'badge-critical'}`}>{saveStatus.msg}</span>}
                <select value={saveMode} onChange={(e) => setSaveMode(e.target.value as SaveMode)} className="corp-input h-9 w-32">
                  <option value="dory">Index</option>
                  <option value="local">Export</option>
                </select>
                <button type="button" onClick={handleSave} disabled={saving || (!active.content.trim() && saveMode !== 'local')} className="btn-primary h-9">
                  {saveMode === 'local' ? <Download size={14} /> : <Save size={14} />}
                  {saving ? 'Saving...' : saveMode === 'local' ? 'Export' : 'Save'}
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {!preview ? (
                <div className="mx-auto max-w-3xl px-6 py-8">
                  <input
                    ref={titleRef}
                    className="w-full border-0 bg-transparent text-4xl font-extrabold text-[var(--text-1)] outline-none placeholder:text-[var(--text-4)]"
                    placeholder="Untitled"
                    value={active.title}
                    onChange={(e) => updateNote(active.id, { title: e.target.value })}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); editorRef.current?.focus(); } }}
                  />
                  <div className="my-5 h-px bg-[var(--border)]" />
                  <div className="relative">
                    <textarea
                      ref={editorRef}
                      className="min-h-[440px] w-full resize-none border-0 bg-transparent text-base leading-8 text-[var(--text-2)] outline-none placeholder:text-[var(--text-4)]"
                      placeholder="Write something, or type / for blocks..."
                      value={active.content}
                      onChange={(e) => handleContentChange(e.target.value, e.target)}
                      onKeyDown={(e) => { if (e.key === 'Escape') setSlashVisible(false); }}
                      spellCheck
                    />
                    {slashVisible && filteredSlash.length > 0 && (
                      <div className="app-card absolute left-0 top-8 z-30 min-w-56 overflow-hidden py-1 shadow-[var(--shadow)]">
                        <p className="app-label px-3 py-2">Insert block</p>
                        {filteredSlash.slice(0, 8).map((command) => (
                          <button
                            key={command.cmd}
                            type="button"
                            className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm text-[var(--text-2)] hover:bg-[var(--surface-2)]"
                            onMouseDown={(e) => { e.preventDefault(); applySlash(command.insert); }}
                          >
                            <span className="flex h-6 w-7 items-center justify-center rounded bg-[var(--accent-soft)] text-xs font-bold text-[var(--accent)]">{command.icon}</span>
                            <span className="flex-1">{command.label}</span>
                            <span className="text-xs text-[var(--text-4)]">{command.cmd}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="mx-auto max-w-3xl px-6 py-8">
                  <h1 className="mb-6 text-4xl font-extrabold text-[var(--text-1)]">{active.title || 'Untitled'}</h1>
                  <div className="md-preview" dangerouslySetInnerHTML={{ __html: renderedHtml }} />
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
            <FileText size={38} className="text-[var(--text-4)]" />
            <p className="font-bold text-[var(--text-1)]">No note selected</p>
            <button type="button" onClick={handleNewNote} className="btn-primary"><Plus size={15} /> New note</button>
          </div>
        )}
      </section>
    </div>
  );
}
