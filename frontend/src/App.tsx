import { useEffect, useState } from 'react';
import { useAuth } from './auth/useAuth';
import { SessionProvider } from './state/SessionContext';
import { useSession } from './state/SessionContext';
import { useAdminStore } from './state/adminStore';
import { AppShell } from './components/AppShell';
import { SessionList } from './components/SessionList';
import { ChatView } from './components/ChatView';
import { HomeScreen } from './components/HomeScreen';
import { TipsView } from './components/TipsView';
import { IdeasView } from './components/IdeasView';
import { IntakeView } from './components/IntakeView';
import { TopBar } from './components/TopBar';
import { AdminPanel } from './components/AdminPanel';
import { getProfile, getAdminAccess, listUserIdeas } from './api/client';
import { useProfileCache } from './state/profileCache';
import type { UserProfile } from './api/types';

function AppContent() {
  const { loadSessions, deselectSession, startTypedSession, state } = useSession();
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [showTips, setShowTips] = useState(false);
  const [showIdeas, setShowIdeas] = useState(false);
  const [ideaCount, setIdeaCount] = useState(0);
  const setIsAdmin = useAdminStore((s) => s.setIsAdmin);
  const isAdmin = useAdminStore((s) => s.isAdmin);

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
          // Seed the profile cache so ProfileChip doesn't re-fetch for the current user
          useProfileCache.getState().set(p.user_id, {
            user_id: p.user_id,
            name: p.name,
            title: p.title,
            department: p.department,
            avatar_url: p.avatar_url,
            team: p.team,
          });
        })
        .catch((err) => {
          if (err?.message?.includes('401')) return;
          setProfileLoaded(true);
        });
    }
  }, [user]);

  // Load idea count
  useEffect(() => {
    if (user && profileLoaded) {
      listUserIdeas().then((ideas) => setIdeaCount(ideas.length)).catch(() => {});
    }
  }, [user, profileLoaded]);

  // Clear tips/ideas view when a session becomes active
  useEffect(() => {
    if (state.activeSessionId) {
      setShowTips(false);
      setShowIdeas(false);
    }
  }, [state.activeSessionId]);

  // Check admin access on mount
  useEffect(() => {
    if (user) {
      getAdminAccess()
        .then(({ is_admin }) => setIsAdmin(is_admin))
        .catch(() => {});
    }
  }, [user, setIsAdmin]);

  if (!profileLoaded) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--color-surface)' }}>
        <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-primary)' }} />
      </div>
    );
  }

  const intakeComplete = profile?.intake_completed_at != null;

  if (!intakeComplete) {
    return (
      <IntakeView
        onComplete={() => {
          getProfile()
            .then((p) => setProfile(p))
            .catch(() => {});
        }}
      />
    );
  }

  if (showAdmin && isAdmin) {
    return (
      <div className="flex flex-col h-screen">
        <TopBar onAdminClick={() => setShowAdmin(false)} profile={profile} />
        <AdminPanel onBack={() => setShowAdmin(false)} />
      </div>
    );
  }

  const handleGoHome = () => {
    deselectSession();
    setShowTips(false);
    setShowIdeas(false);
  };

  const sidebar = (
    <div className="flex flex-col h-full">
      <div className="flex-1 min-h-0">
        <SessionList
          onGoHome={handleGoHome}
          onShowIdeas={() => { deselectSession(); setShowTips(false); setShowIdeas(true); }}
          showIdeas={showIdeas && !state.activeSessionId}
          ideaCount={ideaCount}
        />
      </div>
    </div>
  );

  const content = state.activeSessionId
    ? <ChatView onShowTips={() => { deselectSession(); setShowTips(true); setShowIdeas(false); }} />
    : showIdeas
      ? <IdeasView onBack={() => setShowIdeas(false)} onChatWithIdea={() => { setShowIdeas(false); startTypedSession('chat'); }} />
      : showTips
        ? <TipsView onBack={() => setShowTips(false)} userDepartment={profile?.department} />
        : <HomeScreen onShowTips={() => setShowTips(true)} />;

  return (
    <div className="flex flex-col h-screen">
      <TopBar onAdminClick={() => setShowAdmin(true)} profile={profile} />
      <div className="flex-1 min-h-0">
        <AppShell sidebar={sidebar} content={content} />
      </div>
    </div>
  );
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
