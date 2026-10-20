import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { AppShell } from '@/components/layout/AppShell';
import { Dashboard } from '@/pages/Dashboard';
import { SearchPage } from '@/pages/SearchPage';
import { QuizPage } from '@/pages/QuizPage';
import { ReviewPage } from '@/pages/ReviewPage';
import { LibraryPage } from '@/pages/LibraryPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { CalendarPage } from '@/pages/CalendarPage';
import { NoteEditorPage } from '@/pages/NoteEditorPage';
import { PomodoroPage } from '@/pages/PomodoroPage';
import { LoginPage } from '@/pages/LoginPage';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';

const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.18, ease: 'easeOut' } },
  exit:    { opacity: 0, y: -6, transition: { duration: 0.12, ease: 'easeIn' } },
};

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div key={location.pathname} variants={pageVariants} initial="initial" animate="animate" exit="exit" className="h-full">
        <Routes location={location}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/*" element={
            <ProtectedRoute>
              <AppShell>
                <ErrorBoundary>
                  <Routes>
                    <Route path="/"         element={<Dashboard />} />
                    <Route path="/search"   element={<SearchPage />} />
                    <Route path="/quiz"     element={<QuizPage />} />
                    <Route path="/review"   element={<ReviewPage />} />
                    <Route path="/library"  element={<LibraryPage />} />
                    <Route path="/calendar" element={<CalendarPage />} />
                    <Route path="/notes"    element={<NoteEditorPage />} />
                    <Route path="/pomodoro" element={<PomodoroPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="*" element={
                      <div className="app-card p-10 text-center">
                        <p className="font-bold text-[var(--text-1)]">Page not found</p>
                        <p className="mt-1 text-sm text-[var(--text-3)]">Use the sidebar to return to an Engram workspace.</p>
                      </div>
                    } />
                  </Routes>
                </ErrorBoundary>
              </AppShell>
            </ProtectedRoute>
          } />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AnimatedRoutes />
    </AuthProvider>
  );
}
