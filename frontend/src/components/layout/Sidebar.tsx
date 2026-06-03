import { NavLink, useNavigate } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { Settings, LogOut, Gauge } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { navGroups } from './navConfig';

/** One-row account control: avatar + name (left) + Settings + Logout icons (right).
 *  Always pinned at the bottom of the sidebar regardless of page scroll. */
function AccountRow() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function onClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [menuOpen]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setMenuOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors hover:bg-[var(--surface-2)]"
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] font-bold text-[var(--accent)]">
          {(user?.name?.[0] ?? 'D').toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold text-[var(--text-1)]">{user?.name ?? 'Demo User'}</p>
          <p className="truncate text-xs text-[var(--text-3)]">{user?.email ?? 'demo@dory.md'}</p>
        </div>
      </button>

      {menuOpen && (
        <div className="absolute bottom-full left-0 right-0 mb-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-lg overflow-hidden">
          <button
            type="button"
            onClick={() => { setMenuOpen(false); navigate('/settings'); }}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm font-medium text-[var(--text-1)] hover:bg-[var(--surface-2)]"
          >
            <Settings size={15} className="text-[var(--text-3)]" /> Settings
          </button>
          <button
            type="button"
            onClick={() => { setMenuOpen(false); void logout(); }}
            className="flex w-full items-center gap-2 border-t border-[var(--border)] px-3 py-2 text-sm font-medium text-[var(--text-1)] hover:bg-[var(--surface-2)]"
          >
            <LogOut size={15} className="text-[var(--text-3)]" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 border-r border-[var(--border)] bg-[oklch(var(--background)/0.62)] px-3 py-4 md:flex md:flex-col">
      {/* AppShell gives this aside a fixed viewport-minus-header height; the nav scrolls inside, the AccountRow stays pinned. */}
      <div className="flex-1 space-y-5 overflow-y-auto">
        {navGroups.map((group) => (
          <div key={group.label}>
            <p className="app-label mb-2 px-2">{group.label}</p>
            <nav className="space-y-1">
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
            </nav>
          </div>
        ))}

        <div className="app-card-muted p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-bold text-[var(--text-1)]">
            <Gauge size={16} className="text-[var(--accent)]" />
            Daily loop
          </div>
          <div className="space-y-2 text-xs text-[var(--text-2)]">
            <div className="flex items-center justify-between">
              <span>Capture</span>
              <span className="font-bold text-[var(--good)]">ready</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Review</span>
              <span className="font-bold text-[var(--warn)]">queued</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Practice</span>
              <span className="font-bold text-[var(--accent)]">adaptive</span>
            </div>
          </div>
        </div>
      </div>

      {/* Account row pinned at the bottom — single row, click to reveal Settings/Sign out */}
      <div className="mt-3 border-t border-[var(--border)] pt-3">
        <AccountRow />
      </div>
    </aside>
  );
}
