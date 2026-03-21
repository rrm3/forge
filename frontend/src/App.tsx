import { useEffect, useState } from 'react';
import { useAuth } from './auth/useAuth';
import { SessionProvider } from './state/SessionContext';
import { useSession } from './state/SessionContext';
import { AppShell } from './components/AppShell';
import { SessionList } from './components/SessionList';
import { ChatView } from './components/ChatView';
import { HomeScreen } from './components/HomeScreen';
import { IntakeView } from './components/IntakeView';
import { UserMenu } from './components/UserMenu';
import { getProfile } from './api/client';
import type { UserProfile } from './api/types';

function AppContent() {
  const { loadSessions, state } = useSession();
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Load profile to check intake status
  useEffect(() => {
    if (user) {
      getProfile()
        .then((p) => {
          setProfile(p);
          setProfileLoaded(true);
        })
        .catch((err) => {
          // If 401, the auth layer will handle redirect - don't show intake
          if (err?.message?.includes('401')) return;
          // Other errors (e.g., profile doesn't exist yet) - proceed to intake
          setProfileLoaded(true);
        });
    }
  }, [user]);

  // Re-check profile after streaming completes (catches intake completion)
  useEffect(() => {
    if (user && !state.isStreaming && profileLoaded && !profile?.intake_completed_at) {
      getProfile()
        .then((p) => setProfile(p))
        .catch(() => {});
    }
  }, [user, state.isStreaming, profileLoaded, profile?.intake_completed_at]);

  // Wait for profile to load before deciding what to show
  if (!profileLoaded) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--color-surface)' }}>
        <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-primary)' }} />
      </div>
    );
  }

  // Check if intake is complete
  const intakeComplete = profile?.intake_completed_at != null;

  // Show intake view if not complete
  if (!intakeComplete) {
    return <IntakeView />;
  }

  // Normal app with sidebar
  const sidebar = (
    <div className="flex flex-col h-full">
      <div className="flex-1 min-h-0">
        <SessionList />
      </div>
      <UserMenu />
    </div>
  );

  const content = state.activeSessionId ? <ChatView /> : <HomeScreen />;

  return <AppShell sidebar={sidebar} content={content} />;
}

function App() {
  const { isAuthenticated, isLoading, signIn, authError } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !authError) {
      signIn();
    }
  }, [isLoading, isAuthenticated, authError, signIn]);

  if (authError) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--color-surface)' }}>
        <div className="w-full max-w-sm bg-white rounded-xl shadow-sm border p-8 text-center" style={{ borderColor: 'var(--color-border)' }}>
          <p className="text-sm mb-4" style={{ color: 'var(--color-error)' }}>{authError}</p>
          <button
            onClick={signIn}
            className="py-2 px-4 text-white text-sm font-medium rounded-lg transition-colors"
            style={{ backgroundColor: 'var(--color-primary)' }}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--color-surface)' }}>
        <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-primary)' }} />
      </div>
    );
  }

  return (
    <SessionProvider>
      <AppContent />
    </SessionProvider>
  );
}

export default App;
