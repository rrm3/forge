import { useEffect, useState, useRef } from 'react';
import { Routes, Route, Navigate, Outlet, useNavigate, useLocation, useParams } from 'react-router-dom';
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

/** Syncs the :sessionId URL param to the session context. */
function ChatRoute() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { selectSession, state } = useSession();
  const loadingRef = useRef<string | null>(null);

  useEffect(() => {
    if (sessionId && state.activeSessionId !== sessionId && loadingRef.current !== sessionId) {
      loadingRef.current = sessionId;
      selectSession(sessionId).finally(() => {
        loadingRef.current = null;
      });
    }
  }, [sessionId, selectSession, state.activeSessionId]);

  return <ChatView />;
}

/** Wraps TipsView and passes the optional tipId from the URL path. */
function TipsRoute({ userDepartment }: { userDepartment?: string }) {
  const { '*': splat } = useParams();
  const tipId = splat || undefined;
  return <TipsView userDepartment={userDepartment} initialTipId={tipId} />;
}

/** Main layout with sidebar, used for all post-intake routes. */
function MainLayout({ profile, ideaCount }: { profile: UserProfile | null; ideaCount: number }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, deselectSession } = useSession();
  const prevActiveIdRef = useRef<string | null>(null);

  // When a new session is created (via WS), navigate to its chat URL
  useEffect(() => {
    const prev = prevActiveIdRef.current;
    prevActiveIdRef.current = state.activeSessionId;

    if (
      state.activeSessionId &&
      state.activeSessionId !== prev &&
      location.pathname !== `/chat/${state.activeSessionId}`
    ) {
      navigate(`/chat/${state.activeSessionId}`);
    }
  }, [state.activeSessionId, location.pathname, navigate]);

  // Deselect session when navigating away from a chat route.
  // Only react to location changes - not activeSessionId changes - to avoid
  // racing with the navigation effect during session creation.
  useEffect(() => {
    if (!location.pathname.startsWith('/chat/') && state.activeSessionId) {
      deselectSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const sidebar = (
    <div className="flex flex-col h-full">
      <div className="flex-1 min-h-0">
        <SessionList ideaCount={ideaCount} />
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-screen">
      <TopBar profile={profile} />
      <div className="flex-1 min-h-0">
        <AppShell sidebar={sidebar} content={<Outlet />} />
      </div>
    </div>
  );
}

function AppContent() {
  const { loadSessions, state } = useSession();
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
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

  const intakeComplete = profile?.intake_completed_at != null || state.intakeComplete;

  return (
    <Routes>
      {/* Intake / Day 1 - redirects home if already completed */}
      <Route
        path="/day1"
        element={
          intakeComplete
            ? <Navigate to="/" replace />
            : <IntakeView onComplete={() => {
                getProfile().then((p) => setProfile(p)).catch(() => {});
              }} />
        }
      />

      {/* Admin */}
      <Route
        path="/admin"
        element={
          isAdmin ? (
            <div className="flex flex-col h-screen">
              <TopBar profile={profile} />
              <AdminPanel />
            </div>
          ) : (
            <Navigate to="/" replace />
          )
        }
      />

      {/* Main layout (all post-intake routes) */}
      <Route
        path="/*"
        element={
          !intakeComplete
            ? <Navigate to="/day1" replace />
            : <MainLayout profile={profile} ideaCount={ideaCount} />
        }
      >
        <Route index element={<HomeScreen />} />
        <Route path="chat/:sessionId" element={<ChatRoute />} />
        <Route path="tips/*" element={<TipsRoute userDepartment={profile?.department} />} />
        <Route path="ideas" element={<IdeasView />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
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
