import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Loader2, Brain, CheckCircle2, Activity, Search, BrainCircuit } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

export function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  function switchMode(next: 'login' | 'register') {
    setMode(next);
    setError('');
    setSuccess('');
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    if (mode === 'login') {
      const ok = await login(email, password);
      setLoading(false);
      if (!ok) {
        setError('Invalid email or password.');
        return;
      }
      navigate('/');
      return;
    }

    if (name.trim().length < 2) {
      setError('Name must be at least 2 characters.');
      setLoading(false);
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      setLoading(false);
      return;
    }

    const result = await register(name.trim(), email, password);
    setLoading(false);
    if (result !== true) {
      setError(result);
      return;
    }
    navigate('/');
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] p-4 text-[var(--text-1)]">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-6xl overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)] lg:grid-cols-[1.05fr_0.95fr]">
        <section className="relative flex flex-col justify-between bg-hero p-8 text-background">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-lavender text-hero animate-float">
              <Brain size={20} />
            </span>
            <div>
              <p className="text-lg font-bold tracking-[-0.02em]">Dory.md</p>
              <p className="text-sm text-background/60">The notes app that remembers with you.</p>
            </div>
          </div>

          <div className="my-12 max-w-xl">
            <p className="app-label mb-3">Memory OS</p>
            <h1 className="text-4xl font-bold tracking-[-0.02em] leading-[1.08]">Track what you know before it quietly fades.</h1>
            <p className="mt-4 text-lg leading-8 text-background/70">
              Dory turns files and notes into memory chunks, models retention decay, and gives you the next best review action.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { icon: Activity, label: 'Decay engine', text: 'Retention per chunk' },
              { icon: Search, label: 'Hybrid search', text: 'Find related ideas' },
              { icon: BrainCircuit, label: 'Quiz mode', text: 'Practice weak spots' },
            ].map(({ icon: Icon, label, text }) => (
              <div key={label} className="app-card p-4">
                <Icon size={18} className="text-[var(--accent)]" />
                <p className="mt-3 font-bold">{label}</p>
                <p className="mt-1 text-sm text-[var(--text-3)]">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mesh-bg flex items-center justify-center p-6">
          <div className="w-full max-w-md">
            <div className="mb-6">
              <h2 className="text-2xl font-extrabold">{mode === 'login' ? 'Welcome back' : 'Create account'}</h2>
              <p className="mt-1 text-sm text-[var(--text-3)]">
                {mode === 'login' ? 'Sign in to continue your recall loop.' : 'Start tracking memory health in your notes.'}
              </p>
            </div>

            <div className="mb-5 grid grid-cols-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-1">
              <button
                type="button"
                onClick={() => switchMode('login')}
                className={mode === 'login' ? 'btn-primary' : 'btn-ghost'}
              >
                Sign in
              </button>
              <button
                type="button"
                onClick={() => switchMode('register')}
                className={mode === 'register' ? 'btn-primary' : 'btn-ghost'}
              >
                Register
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'register' && (
                <label className="block">
                  <span className="mb-1 block text-sm font-bold text-[var(--text-2)]">Full name</span>
                  <input className="corp-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" required autoFocus />
                </label>
              )}

              <label className="block">
                <span className="mb-1 block text-sm font-bold text-[var(--text-2)]">Email</span>
                <input className="corp-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required autoFocus={mode === 'login'} />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-bold text-[var(--text-2)]">Password</span>
                <div className="relative">
                  <input
                    className="corp-input pr-10"
                    type={showPass ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Minimum 6 characters"
                    required
                    minLength={mode === 'register' ? 6 : undefined}
                  />
                  <button type="button" onClick={() => setShowPass((v) => !v)} className="btn-ghost absolute right-1 top-1 h-8 w-8 p-0">
                    {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </label>

              {error && <div className="rounded-lg border border-destructive/25 bg-destructive/10 p-3 text-sm font-bold text-destructive">{error}</div>}
              {success && (
                <div className="flex items-center gap-2 rounded-lg border border-[color-mix(in_oklab,var(--good)_25%,transparent)] bg-[color-mix(in_oklab,var(--good)_8%,transparent)] p-3 text-sm font-bold text-[var(--good)]">
                  <CheckCircle2 size={15} /> {success}
                </div>
              )}

              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading && <Loader2 size={16} className="animate-spin" />}
                {mode === 'login' ? 'Sign in' : 'Create account'}
              </button>
            </form>

            <div className="mt-5 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3">
              <p className="text-xs font-bold text-[var(--text-3)]">Demo credentials</p>
              <p className="mt-1 font-mono text-sm text-[var(--text-2)]">demo@dory.md / demo123</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
