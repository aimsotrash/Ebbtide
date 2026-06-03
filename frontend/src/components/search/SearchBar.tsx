import { useState, useRef, useEffect } from 'react';
import { Search, X, Loader2, Command } from 'lucide-react';
import { debounce } from '@/lib/utils';

interface SearchBarProps {
  onSearch: (query: string) => void;
  loading?: boolean;
  initialValue?: string;
  placeholder?: string;
}

const SUGGESTIONS = [
  'forgetting curve',
  'review tomorrow',
  'machine learning',
  'project notes',
  'critical retention',
];

export function SearchBar({ onSearch, loading, initialValue = '', placeholder }: SearchBarProps) {
  const [query, setQuery] = useState(initialValue);
  const [focused, setFocused] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debouncedSearch = useRef(debounce(onSearch, 350));

  useEffect(() => {
    debouncedSearch.current = debounce(onSearch, 350);
  }, [onSearch]);

  useEffect(() => {
    setQuery(initialValue);
  }, [initialValue]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  function handleChange(value: string) {
    setQuery(value);
    if (value.trim().length >= 2) debouncedSearch.current(value.trim());
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
      setShowSuggestions(false);
    }
  }

  function clear() {
    setQuery('');
    onSearch('');
    inputRef.current?.focus();
  }

  return (
    <div className="relative">
      <form onSubmit={handleSubmit}>
        <div
          className={`flex items-center gap-3 rounded-lg border px-4 py-3 transition ${
            focused
              ? 'border-[var(--accent-border)] bg-[var(--surface)] shadow-[0_0_0_3px_oklch(var(--ring)/0.18)]'
              : 'border-[var(--border)] bg-[var(--surface-2)] hover:border-[var(--border-strong)]'
          }`}
        >
          {loading ? <Loader2 size={17} className="animate-spin text-[var(--accent)]" /> : <Search size={17} className="text-[var(--text-3)]" />}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => handleChange(e.target.value)}
            onFocus={() => { setFocused(true); setShowSuggestions(true); }}
            onBlur={() => { setFocused(false); window.setTimeout(() => setShowSuggestions(false), 150); }}
            placeholder={placeholder ?? 'Search your memories...'}
            className="min-w-0 flex-1 bg-transparent text-sm text-[var(--text-1)] outline-none placeholder:text-[var(--text-4)]"
          />
          {query ? (
            <button type="button" onClick={clear} className="btn-ghost h-7 w-7 p-0" title="Clear search">
              <X size={14} />
            </button>
          ) : (
            <span className="hidden items-center gap-1 text-xs font-bold text-[var(--text-4)] sm:flex">
              <Command size={12} /> K
            </span>
          )}
        </div>
      </form>

      {showSuggestions && !query && (
        <div className="app-card absolute left-0 right-0 top-full z-10 mt-2 overflow-hidden py-1 shadow-[var(--shadow)]">
          <p className="app-label px-3 py-2">Try searching</p>
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--text-2)] hover:bg-[var(--surface-2)]"
              onClick={() => {
                setQuery(suggestion);
                onSearch(suggestion);
                setShowSuggestions(false);
                inputRef.current?.blur();
              }}
            >
              <Search size={14} className="text-[var(--text-3)]" />
              {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
