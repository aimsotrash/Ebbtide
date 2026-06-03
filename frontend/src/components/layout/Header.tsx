import { Brain, Bell, Plus, Upload, X, Menu, Settings } from 'lucide-react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { ingestText } from '@/lib/api';
import { UploadModal } from '@/components/upload/UploadModal';
import { navGroups } from './navConfig';

interface HeaderProps {
  hasDiscovery?: boolean;
  onDiscoveryClick?: () => void;
}

const pageMeta: Record<string, { title: string; detail: string }> = {
  '/': { title: 'Memory health', detail: 'Watch retention, risk, and review timing.' },
  '/search': { title: 'Discovery search', detail: 'Find the right chunk before it fades.' },
  '/quiz': { title: 'Practice', detail: 'Turn weak memories into stronger ones.' },
  '/library': { title: 'Library', detail: 'Browse, organize, edit, and protect chunks.' },
  '/notes': { title: 'Write', detail: 'Draft notes and index them into Dory.' },
  '/pomodoro': { title: 'Focus timer', detail: 'Work in sessions while your notes stay nearby.' },
  '/calendar': { title: 'Review calendar', detail: 'See when concepts are predicted to fall off.' },
  '/settings': { title: 'Settings', detail: 'Tune reminders, demo data, and account controls.' },
};

export function Header({ hasDiscovery, onDiscoveryClick }: HeaderProps) {
  const [showIngest, setShowIngest] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [ingestContent, setIngestContent] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [ingestSuccess, setIngestSuccess] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();
  const meta = pageMeta[location.pathname] ?? pageMeta['/'];

  // Close the mobile nav whenever the route changes.
  useEffect(() => { setMobileNavOpen(false); }, [location.pathname]);

  async function handleIngest() {
    if (!ingestContent.trim()) return;
    setIngesting(true);
    try {
      await ingestText(ingestContent.trim());
      setIngestSuccess(true);
      setIngestContent('');
      window.setTimeout(() => {
        setIngestSuccess(false);
        setShowIngest(false);
      }, 1100);
    } finally {
      setIngesting(false);
    }
  }

  return (
    <>
      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-[var(--border)] bg-[oklch(var(--background)/0.92)] px-4 backdrop-blur md:px-6">
        <div className="flex min-w-0 items-center gap-4">
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            className="btn-ghost h-9 w-9 p-0 md:hidden"
            aria-label="Open navigation menu"
            aria-expanded={mobileNavOpen}
          >
            <Menu size={18} />
          </button>
          <Link to="/" className="flex shrink-0 items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
              <Brain size={18} />
            </span>
            <span className="hidden font-bold text-[var(--text-1)] sm:inline">Dory.md</span>
          </Link>
          <div className="hidden min-w-0 border-l border-[var(--border)] pl-4 md:block">
            <p className="text-sm font-bold text-[var(--text-1)]">{meta.title}</p>
            <p className="truncate text-xs text-[var(--text-3)]">{meta.detail}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setShowUpload(true)} className="btn-secondary">
            <Upload size={15} />
            <span className="hidden sm:inline">Upload</span>
          </button>
          <button type="button" onClick={() => setShowIngest(true)} className="btn-primary">
            <Plus size={15} />
            <span>Add memory</span>
          </button>
          <button
            type="button"
            onClick={onDiscoveryClick}
            className="btn-ghost relative h-9 w-9 p-0"
            title="Discovery notifications"
            aria-label={hasDiscovery ? 'Discovery notifications (new)' : 'Discovery notifications'}
          >
            <Bell size={16} />
            {hasDiscovery && <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[var(--warn)]" />}
          </button>
        </div>
      </header>

      {/* Mobile navigation drawer — the sidebar is desktop-only, so this is the
          sole way to navigate on phones (UI_REVIEW U-1). */}
      {mobileNavOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
          onClick={(e) => { if (e.target === e.currentTarget) setMobileNavOpen(false); }}
        >
          <div className="absolute inset-0 bg-black/35" />
          <nav className="absolute left-0 top-0 h-full w-72 max-w-[80vw] overflow-y-auto border-r border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow)]">
            <div className="mb-4 flex items-center justify-between">
              <span className="flex items-center gap-2 font-bold text-[var(--text-1)]">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
                  <Brain size={16} />
                </span>
                Dory.md
              </span>
              <button type="button" onClick={() => setMobileNavOpen(false)} className="btn-ghost h-8 w-8 p-0" aria-label="Close navigation menu">
                <X size={16} />
              </button>
            </div>
            <div className="space-y-5">
              {navGroups.map((group) => (
                <div key={group.label}>
                  <p className="app-label mb-2 px-2">{group.label}</p>
                  <div className="space-y-1">
                    {group.items.map(({ to, label, icon: Icon, exact }) => (
                      <NavLink
                        key={to}
                        to={to}
                        end={exact}
                        className={({ isActive }) => (isActive ? 'nav-item-active' : 'nav-item')}
                      >
                        <Icon size={17} />
                        <span>{label}</span>
                      </NavLink>
                    ))}
                  </div>
                </div>
              ))}
              <div>
                <p className="app-label mb-2 px-2">Account</p>
                <NavLink to="/settings" className={({ isActive }) => (isActive ? 'nav-item-active' : 'nav-item')}>
                  <Settings size={17} />
                  <span>Settings</span>
                </NavLink>
              </div>
            </div>
          </nav>
        </div>
      )}

      {showIngest && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowIngest(false);
          }}
        >
          <div className="app-card w-full max-w-xl p-5 shadow-[var(--shadow)]">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-bold text-[var(--text-1)]">Add a memory</h3>
                <p className="text-sm text-[var(--text-3)]">Paste a fragment, idea, or note. Dory will chunk and track it.</p>
              </div>
              <button type="button" onClick={() => setShowIngest(false)} className="btn-ghost h-8 w-8 p-0" title="Close">
                <X size={16} />
              </button>
            </div>
            <textarea
              className="corp-input min-h-40 resize-none leading-relaxed"
              placeholder="Paste notes, transcript fragments, formulas, or anything you want to remember."
              value={ingestContent}
              onChange={(e) => setIngestContent(e.target.value)}
              autoFocus
            />
            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <button type="button" className="btn-ghost justify-start" onClick={() => { setShowIngest(false); setShowUpload(true); }}>
                <Upload size={14} />
                Upload a file instead
              </button>
              <div className="flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => setShowIngest(false)}>
                  Cancel
                </button>
                <button type="button" className="btn-primary" onClick={handleIngest} disabled={ingesting || !ingestContent.trim()}>
                  {ingesting ? 'Processing...' : ingestSuccess ? 'Saved' : 'Remember this'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} />}
    </>
  );
}
