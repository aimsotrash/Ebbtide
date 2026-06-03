import { useState, useEffect } from 'react';
import {
  Pencil, Trash2, FolderOpen, Lock, Unlock, Eye, EyeOff,
  Save, X, Loader2, Brain, Clock, TrendingDown, Sparkles,
  BookOpen, Layers, Check, Download, ChevronDown,
} from 'lucide-react';
import { cn, formatRetentionPct } from '@/lib/utils';
import {
  getChunkDetail, updateChunk, deleteChunk,
  moveChunkToFolder, aiSummarize, aiExpand, aiOptimize,
  ingestText,
} from '@/lib/api';
import { retentionToColor, retentionToLabel, categoryColors } from '@/styles/theme';
import type { Category } from '@/lib/types';

const ENC_PREFIX = 'ENC:';

async function encryptContent(content: string, password: string): Promise<string> {
  const enc = new TextEncoder();
  const km = await crypto.subtle.importKey('raw', enc.encode(password), { name: 'PBKDF2' }, false, ['deriveKey']);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 100_000, hash: 'SHA-256' },
    km, { name: 'AES-GCM', length: 256 }, false, ['encrypt'],
  );
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, enc.encode(content));
  const combined = new Uint8Array(16 + 12 + ct.byteLength);
  combined.set(salt, 0);
  combined.set(iv, 16);
  combined.set(new Uint8Array(ct), 28);
  return ENC_PREFIX + btoa(String.fromCharCode(...combined));
}

async function decryptContent(enc: string, password: string): Promise<string> {
  const combined = Uint8Array.from(atob(enc.slice(ENC_PREFIX.length)), (c) => c.charCodeAt(0));
  const salt = combined.slice(0, 16);
  const iv = combined.slice(16, 28);
  const ct = combined.slice(28);
  const e = new TextEncoder();
  const km = await crypto.subtle.importKey('raw', e.encode(password), { name: 'PBKDF2' }, false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 100_000, hash: 'SHA-256' },
    km, { name: 'AES-GCM', length: 256 }, false, ['decrypt'],
  );
  return new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ct));
}

export interface PanelChunk {
  id: string;
  source_file: string;
  category?: string | null;
  retention?: number;
  access_count: number;
  last_accessed: string;
  folder?: string | null;
  content: string;
}

interface NoteDetailPanelProps {
  chunk: PanelChunk;
  folders?: string[];
  onDelete?: (id: string) => void;
  onContentUpdate?: (id: string, content: string) => void;
  onFolderChange?: (id: string, folder: string | null) => void;
}

type AIPhase = 'idle' | 'summarizing' | 'summarized' | 'expanding' | 'expanded' | 'optimizing' | 'optimized';

function baseName(path: string) {
  return path.split(/[\\/]/).pop() ?? path;
}

function ActionButton({
  active,
  children,
  onClick,
  disabled,
}: {
  active?: boolean;
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn('btn-secondary h-9', active && 'border-[var(--accent-border)] bg-[var(--accent-soft)] text-[var(--accent)]')}
    >
      {children}
    </button>
  );
}

export function NoteDetailPanel({ chunk, folders = [], onDelete, onContentUpdate, onFolderChange }: NoteDetailPanelProps) {
  const [fullContent, setFullContent] = useState('');
  const [loadingDetail, setLoadingDetail] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [showFolderMenu, setShowFolderMenu] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [encryptModal, setEncryptModal] = useState<'lock' | 'unlock' | null>(null);
  const [encryptPw, setEncryptPw] = useState('');
  const [encryptConfirm, setEncryptConfirm] = useState('');
  const [encryptError, setEncryptError] = useState('');
  const [encryptBusy, setEncryptBusy] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [decryptedView, setDecryptedView] = useState<string | null>(null);
  const [aiPhase, setAiPhase] = useState<AIPhase>('idle');
  const [aiError, setAiError] = useState('');
  const [summary, setSummary] = useState('');
  const [expanded, setExpanded] = useState('');
  const [optimized, setOptimized] = useState('');
  const [savedOptimized, setSavedOptimized] = useState(false);

  useEffect(() => {
    setLoadingDetail(true);
    setEditMode(false);
    setDecryptedView(null);
    setAiPhase('idle');
    setSummary('');
    setExpanded('');
    setOptimized('');
    setSavedOptimized(false);
    getChunkDetail(chunk.id)
      .then((detail) => setFullContent(detail.content))
      .catch(() => setFullContent(chunk.content))
      .finally(() => setLoadingDetail(false));
  }, [chunk.id, chunk.content]);

  const isEncrypted = fullContent.startsWith(ENC_PREFIX);
  const displayContent = decryptedView ?? (isEncrypted ? null : fullContent);
  const retention = chunk.retention ?? 0.5;
  const color = retentionToColor(retention);
  const category = (chunk.category?.toLowerCase() as Category) ?? 'general';
  const catColor = categoryColors[category] ?? categoryColors.general;
  const aiBusy = aiPhase === 'summarizing' || aiPhase === 'expanding' || aiPhase === 'optimizing';
  const canUseContent = Boolean(displayContent);

  function startEdit() {
    setEditContent(decryptedView ?? fullContent);
    setEditMode(true);
  }

  async function saveEdit() {
    setSaving(true);
    try {
      await updateChunk(chunk.id, editContent);
      setFullContent(editContent);
      onContentUpdate?.(chunk.id, editContent);
      setEditMode(false);
    } finally {
      setSaving(false);
    }
  }

  async function moveTo(folder: string | null) {
    await moveChunkToFolder(chunk.id, folder);
    onFolderChange?.(chunk.id, folder);
    setShowFolderMenu(false);
  }

  async function doDelete() {
    await deleteChunk(chunk.id);
    onDelete?.(chunk.id);
    setConfirmDelete(false);
  }

  async function doEncrypt() {
    if (encryptPw !== encryptConfirm) {
      setEncryptError('Passwords do not match.');
      return;
    }
    if (encryptPw.length < 4) {
      setEncryptError('Use at least 4 characters.');
      return;
    }
    setEncryptBusy(true);
    setEncryptError('');
    try {
      const enc = await encryptContent(fullContent, encryptPw);
      await updateChunk(chunk.id, enc);
      setFullContent(enc);
      onContentUpdate?.(chunk.id, enc);
      setDecryptedView(null);
      setEncryptModal(null);
      setEncryptPw('');
      setEncryptConfirm('');
    } catch {
      setEncryptError('Encryption failed.');
    } finally {
      setEncryptBusy(false);
    }
  }

  async function doDecrypt() {
    setEncryptBusy(true);
    setEncryptError('');
    try {
      setDecryptedView(await decryptContent(fullContent, encryptPw));
      setEncryptModal(null);
      setEncryptPw('');
    } catch {
      setEncryptError('Wrong password.');
    } finally {
      setEncryptBusy(false);
    }
  }

  const contentForAI = decryptedView ?? fullContent;

  async function handleSummarize() {
    setAiPhase('summarizing');
    setAiError('');
    try {
      setSummary(await aiSummarize(contentForAI));
      setAiPhase('summarized');
    } catch {
      setAiError('Summarize failed.');
      setAiPhase('idle');
    }
  }

  async function handleExpand() {
    setAiPhase('expanding');
    setAiError('');
    try {
      setExpanded(await aiExpand(contentForAI));
      setAiPhase('expanded');
    } catch {
      setAiError('Deep dive failed.');
      setAiPhase('idle');
    }
  }

  async function handleOptimize() {
    setAiPhase('optimizing');
    setAiError('');
    try {
      setOptimized(await aiOptimize(contentForAI, expanded));
      setAiPhase('optimized');
    } catch {
      setAiError('Optimize failed.');
      setAiPhase('expanded');
    }
  }

  async function saveOptimized() {
    await ingestText(optimized, 'note', `optimized_${baseName(chunk.source_file)}`);
    setSavedOptimized(true);
  }

  return (
    <div className="flex h-full min-h-[620px] flex-col overflow-hidden bg-[var(--surface)]">
      <div className="border-b border-[var(--border)] px-5 py-4">
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-extrabold text-[var(--text-1)]">{baseName(chunk.source_file)}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {chunk.category && (
                <span className="tag capitalize" style={{ color: catColor, background: `color-mix(in oklab, ${catColor} 8%, transparent)`, borderColor: `color-mix(in oklab, ${catColor} 27%, transparent)` }}>
                  {chunk.category}
                </span>
              )}
              {chunk.folder && <span className="tag"><FolderOpen size={12} /> {chunk.folder}</span>}
              <span className="tag" style={{ color, background: `color-mix(in oklab, ${color} 8%, transparent)`, borderColor: `color-mix(in oklab, ${color} 27%, transparent)` }}>
                {formatRetentionPct(retention)} {retentionToLabel(retention)}
              </span>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <div className="relative">
              <button type="button" onClick={() => setShowFolderMenu((v) => !v)} className="btn-ghost h-9 w-9 p-0" title="Move folder">
                <FolderOpen size={16} />
              </button>
              {showFolderMenu && (
                <div className="app-card absolute right-0 top-11 z-30 min-w-48 overflow-hidden py-1 shadow-[var(--shadow)]">
                  <button type="button" onClick={() => moveTo(null)} className="block w-full px-3 py-2 text-left text-sm text-[var(--text-2)] hover:bg-[var(--surface-2)]">
                    Remove from folder
                  </button>
                  {folders.map((folder) => (
                    <button key={folder} type="button" onClick={() => moveTo(folder)} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--text-2)] hover:bg-[var(--surface-2)]">
                      <FolderOpen size={13} /> {folder}
                      {chunk.folder === folder && <Check size={13} className="ml-auto text-[var(--accent)]" />}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {isEncrypted ? (
              <button
                type="button"
                onClick={() => decryptedView ? setDecryptedView(null) : setEncryptModal('unlock')}
                className="btn-ghost h-9 w-9 p-0 text-[var(--warn)]"
                title={decryptedView ? 'Hide decrypted view' : 'Unlock'}
              >
                {decryptedView ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            ) : (
              <button type="button" onClick={() => setEncryptModal('lock')} className="btn-ghost h-9 w-9 p-0" title="Encrypt">
                <Lock size={16} />
              </button>
            )}

            {!editMode && (!isEncrypted || decryptedView) && (
              <button type="button" onClick={startEdit} className="btn-ghost h-9 w-9 p-0" title="Edit">
                <Pencil size={16} />
              </button>
            )}
            <button type="button" onClick={() => setConfirmDelete(true)} className="btn-ghost h-9 w-9 p-0 text-[var(--danger)]" title="Delete">
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      </div>

      {!editMode && canUseContent && !isEncrypted && (
        <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border)] bg-[var(--surface-2)] px-5 py-3">
          <ActionButton active={aiPhase === 'summarized'} onClick={handleSummarize} disabled={aiBusy}>
            {aiPhase === 'summarizing' ? <Loader2 size={14} className="animate-spin" /> : <BookOpen size={14} />} Summarize
          </ActionButton>
          <ActionButton active={aiPhase === 'expanded'} onClick={handleExpand} disabled={aiBusy}>
            {aiPhase === 'expanding' ? <Loader2 size={14} className="animate-spin" /> : <Layers size={14} />} Go deeper
          </ActionButton>
          {(aiPhase === 'expanded' || aiPhase === 'optimizing' || aiPhase === 'optimized') && (
            <ActionButton active={aiPhase === 'optimized'} onClick={handleOptimize} disabled={aiPhase === 'optimizing'}>
              {aiPhase === 'optimizing' ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Optimize
            </ActionButton>
          )}
          {aiPhase !== 'idle' && (
            <button type="button" onClick={() => { setAiPhase('idle'); setAiError(''); }} className="btn-ghost ml-auto">
              Collapse <ChevronDown size={14} />
            </button>
          )}
          {aiError && <span className="text-sm font-bold text-[var(--danger)]">{aiError}</span>}
        </div>
      )}

      {editMode && (
        <div className="flex items-center justify-end gap-2 border-b border-[var(--border)] bg-[var(--surface-2)] px-5 py-3">
          <button type="button" onClick={() => setEditMode(false)} className="btn-secondary"><X size={14} /> Cancel</button>
          <button type="button" onClick={saveEdit} disabled={saving} className="btn-primary">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {saving ? 'Saving...' : 'Save changes'}
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-5 py-5">
        {loadingDetail ? (
          <div className="flex items-center justify-center py-16"><Loader2 size={22} className="animate-spin text-[var(--accent)]" /></div>
        ) : isEncrypted && !decryptedView ? (
          <div className="mx-auto flex max-w-md flex-col items-center justify-center gap-4 py-20 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-[color-mix(in_oklab,var(--warn)_12%,transparent)] text-[var(--warn)]">
              <Lock size={24} />
            </div>
            <div>
              <p className="font-bold text-[var(--text-1)]">This chunk is encrypted</p>
              <p className="mt-1 text-sm text-[var(--text-3)]">Unlock it locally with the password used to protect it.</p>
            </div>
            <button type="button" onClick={() => setEncryptModal('unlock')} className="btn-primary bg-[var(--warn)] hover:bg-[var(--warn)]">
              <Unlock size={15} /> Unlock
            </button>
          </div>
        ) : editMode ? (
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="corp-input min-h-[460px] resize-none leading-7"
            autoFocus
          />
        ) : (
          <div className="space-y-5">
            <pre className="whitespace-pre-wrap font-sans text-[0.95rem] leading-7 text-[var(--text-2)]">{displayContent}</pre>

            {(aiPhase === 'summarized' || aiPhase === 'expanded' || aiPhase === 'optimized' || aiPhase === 'optimizing') && summary && (
              <div className="rounded-lg border border-[var(--accent-border)] bg-[var(--accent-soft)] p-4">
                <p className="mb-2 flex items-center gap-2 text-sm font-bold text-[var(--accent)]"><BookOpen size={15} /> AI summary</p>
                <p className="text-sm leading-7 text-[var(--text-2)]">{summary}</p>
              </div>
            )}

            {(aiPhase === 'expanded' || aiPhase === 'optimizing' || aiPhase === 'optimized') && expanded && (
              <div className="rounded-lg border border-[color-mix(in_oklab,var(--info)_25%,transparent)] bg-[color-mix(in_oklab,var(--info)_8%,transparent)] p-4">
                <p className="mb-2 flex items-center gap-2 text-sm font-bold text-[var(--info)]"><Layers size={15} /> Deep dive</p>
                <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-[var(--text-2)]">{expanded}</pre>
              </div>
            )}

            {aiPhase === 'optimized' && optimized && (
              <div className="rounded-lg border border-[color-mix(in_oklab,var(--good)_25%,transparent)] bg-[color-mix(in_oklab,var(--good)_8%,transparent)] p-4">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <p className="flex items-center gap-2 text-sm font-bold text-[var(--good)]"><Sparkles size={15} /> Optimized note</p>
                  <button type="button" onClick={saveOptimized} disabled={savedOptimized} className="btn-secondary">
                    {savedOptimized ? <Check size={14} /> : <Download size={14} />}
                    {savedOptimized ? 'Saved' : 'Save as new'}
                  </button>
                </div>
                <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-[var(--text-2)]">{optimized}</pre>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-4 border-t border-[var(--border)] pt-4 text-xs font-bold text-[var(--text-3)]">
              <span className="inline-flex items-center gap-1.5"><Clock size={13} /> {chunk.last_accessed}</span>
              <span className="inline-flex items-center gap-1.5"><TrendingDown size={13} /> {chunk.access_count} reviewed</span>
              <span className="inline-flex items-center gap-1.5"><Brain size={13} /> {baseName(chunk.source_file)}</span>
            </div>
          </div>
        )}
      </div>

      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4">
          <div className="app-card w-full max-w-sm p-5 shadow-[var(--shadow)]">
            <h3 className="font-bold text-[var(--text-1)]">Delete this chunk?</h3>
            <p className="mt-2 text-sm text-[var(--text-3)]">This permanently removes the chunk from the knowledge base.</p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setConfirmDelete(false)} className="btn-secondary">Cancel</button>
              <button type="button" onClick={doDelete} className="btn-primary bg-[var(--danger)] hover:bg-[var(--danger)]">Delete</button>
            </div>
          </div>
        </div>
      )}

      {encryptModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4">
          <div className="app-card w-full max-w-sm p-5 shadow-[var(--shadow)]">
            <div className="mb-3 flex items-center gap-2">
              <Lock size={16} className="text-[var(--warn)]" />
              <h3 className="font-bold text-[var(--text-1)]">{encryptModal === 'lock' ? 'Encrypt chunk' : 'Unlock chunk'}</h3>
            </div>
            <p className="mb-4 text-sm text-[var(--text-3)]">
              {encryptModal === 'lock' ? 'AES-GCM encryption runs in the browser. Keep the password somewhere safe.' : 'Enter the password to decrypt this chunk locally.'}
            </p>
            <div className="space-y-2">
              <div className="relative">
                <input
                  autoFocus
                  type={showPw ? 'text' : 'password'}
                  value={encryptPw}
                  onChange={(e) => { setEncryptPw(e.target.value); setEncryptError(''); }}
                  placeholder="Password"
                  className="corp-input pr-10"
                />
                <button type="button" onClick={() => setShowPw((v) => !v)} className="btn-ghost absolute right-1 top-1 h-8 w-8 p-0">
                  {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              {encryptModal === 'lock' && (
                <input
                  type={showPw ? 'text' : 'password'}
                  value={encryptConfirm}
                  onChange={(e) => { setEncryptConfirm(e.target.value); setEncryptError(''); }}
                  placeholder="Confirm password"
                  className="corp-input"
                />
              )}
              {encryptError && <p className="text-sm font-bold text-[var(--danger)]">{encryptError}</p>}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => { setEncryptModal(null); setEncryptPw(''); setEncryptConfirm(''); setEncryptError(''); }}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={encryptModal === 'lock' ? doEncrypt : doDecrypt}
                disabled={encryptBusy || !encryptPw}
                className="btn-primary bg-[var(--warn)] hover:bg-[var(--warn)]"
              >
                {encryptBusy ? <Loader2 size={14} className="animate-spin" /> : encryptModal === 'lock' ? <Lock size={14} /> : <Unlock size={14} />}
                {encryptModal === 'lock' ? 'Encrypt' : 'Unlock'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
