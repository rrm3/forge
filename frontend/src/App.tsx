import { useEffect, useState, useRef } from 'react';
import { Routes, Route, Navigate, Outlet, useNavigate, useLocation, useParams } from 'react-router-dom';
import { useAuth } from './auth/useAuth';

const LOADING_MESSAGES = [
  'Warming up the neurons...',
  'Brewing a fresh pot of AI...',
  'Convincing the hamsters to run faster...',
  'Reticulating splines...',
  'Calibrating the flux capacitor...',
  'Asking the cloud nicely...',
  'Untangling the neural net...',
  'Feeding the machine learning...',
  'Polishing the algorithms...',
  'Spinning up something clever...',
  'Consulting the oracle...',
  'Organizing the sticky notes...',
  'Defragmenting the imagination...',
  'Loading the good vibes...',
  'Sharpening the pixels...',
  'Tuning the hyperparameters...',
  'Alphabetizing the cloud...',
  'Doing some light reading (all of Wikipedia)...',
  'Putting on our thinking cap...',
  'Compiling the witty remarks...',
  'Herding the electrons...',
  'Folding the paper airplanes...',
  'Optimizing the coffee-to-code ratio...',
  'Shuffling the training data...',
  'Negotiating with the cloud servers...',
  'Downloading more RAM...',
  'Aligning the attention heads...',
  'Crunching the really big numbers...',
  'Warming the GPU seats...',
  'Fluffing the data pillows...',
  'Teaching old models new tricks...',
  'Inflating the word embeddings...',
  'Backpropagating through time...',
  'Searching for the meaning of life (found 42)...',
  'Running on vibes and gradient descent...',
  'Performing interpretive matrix multiplication...',
  'Checking if P equals NP (still no)...',
  'Dusting off the transformer blocks...',
  'Rounding up the floating points...',
  'Counting all the parameters...',
  'Rehearsing small talk...',
  'Stretching before the sprint...',
  'Queuing up the inspiration...',
  'Double-checking the ones and zeros...',
  'Winding up the inference engine...',
  'Preheating the silicon...',
  'Juggling tensors...',
  'Composing a loading haiku...',
  'Synchronizing the butterflies...',
  'Almost there, probably...',
];

/** Loading spinner styled to match DS Identity's auth loading screen. */
function LoadingScreen() {
  const [msgIndex, setMsgIndex] = useState(() => Math.floor(Math.random() * LOADING_MESSAGES.length));

  useEffect(() => {
    const id = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
    }, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'flex-start',
      padding: '80px 20px 20px',
      background: [
        'radial-gradient(circle at 85% 10%, rgba(235, 211, 244, 0.5), transparent 30%)',
        'radial-gradient(circle at 90% 15%, rgba(212, 240, 255, 0.5), transparent 30%)',
        'radial-gradient(circle at 10% 60%, rgba(212, 240, 255, 0.5), transparent 30%)',
        'radial-gradient(circle at 20% 80%, rgba(231, 244, 217, 0.5), transparent 30%)',
        'radial-gradient(circle at 90% 90%, rgba(212, 240, 255, 0.5), transparent 30%)',
        '#f8f9fb',
      ].join(', '),
      backgroundRepeat: 'no-repeat',
      backgroundAttachment: 'fixed',
    }}>
      <style>{`
        @keyframes forge-spin { to { transform: rotate(360deg) } }
        @keyframes forge-fade { 0% { opacity: 0; transform: translateY(4px); } 100% { opacity: 1; transform: translateY(0); } }
      `}</style>
      <div style={{
        width: '100%',
        maxWidth: 476,
        background: '#fff',
        borderRadius: 16,
        boxShadow: '0px 4px 6px -4px rgba(0, 0, 0, 0.1), 0px 1px 29px -3px rgba(0, 0, 0, 0.16)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 16,
        padding: '40px 52px',
      }}>
        <div style={{
          width: 32,
          height: 32,
          border: '3px solid #e5e7eb',
          borderTopColor: '#1a68e8',
          borderRadius: '50%',
          animation: 'forge-spin 0.6s linear infinite',
        }} />
        <div
          key={msgIndex}
          style={{
            fontFamily: 'Satoshi, sans-serif',
            fontSize: 14,
            fontWeight: 500,
            color: '#64748B',
            animation: 'forge-fade 0.3s ease-out',
          }}
        >
          {LOADING_MESSAGES[msgIndex]}
        </div>
      </div>
    </div>
  );
}
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
import { AdminLayout } from './components/AdminLayout';
import { AdminUsers } from './components/AdminUsers';
import { getProfile, getAdminAccess, listUserIdeas } from './api/client';
import { useProfileCache } from './state/profileCache';
import type { UserProfile } from './api/types';

/** Syncs the :sessionId URL param to the session context. */
function ChatRoute() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { selectSession, state } = useSession();

  useEffect(() => {
    // Only load session data when the URL param changes.
    // activeSessionId is intentionally excluded from deps - it changes during
    // WebSocket session creation and would cause a race condition where this
    // effect re-selects the old session before the URL updates.
    if (sessionId && state.activeSessionId !== sessionId) {
      selectSession(sessionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, selectSession]);

  return <ChatView />;
}

/** Wraps TipsView and passes the optional tipId from the URL path. */
function TipsRoute() {
  const { '*': splat } = useParams();
  const tipId = splat || undefined;
  return <TipsView initialTipId={tipId} />;
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
  const setAdminAccess = useAdminStore((s) => s.setAdminAccess);
  const isAdmin = useAdminStore((s) => s.isAdmin);
  const isDepartmentAdmin = useAdminStore((s) => s.isDepartmentAdmin);
  const [adminChecked, setAdminChecked] = useState(false);

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
        .then(({ is_admin, is_department_admin }) => { setAdminAccess(is_admin, is_department_admin); setAdminChecked(true); })
        .catch(() => setAdminChecked(true));
    }
  }, [user, setAdminAccess]);

  if (!profileLoaded) {
    return <LoadingScreen />;
  }

  // For routing: only redirect away from /day1 if the profile was already complete
  // on page load. During the session, IntakeView handles showing the completion card
  // and the user clicks "Let's get started" to navigate away.
  const intakeAlreadyComplete = profile?.intake_completed_at != null;
  const intakeComplete = intakeAlreadyComplete || state.intakeComplete;

  return (
    <Routes>
      {/* Intake / Day 1 - redirects home only if already completed before this session */}
      <Route
        path="/day1"
        element={
          intakeAlreadyComplete
            ? <Navigate to="/" replace />
            : <IntakeView profile={profile} onComplete={() => {
                getProfile().then((p) => setProfile(p)).catch(() => {});
              }} />
        }
      />

      {/* Admin - accessible by full admins and department admins */}
      <Route
        path="/admin/*"
        element={
          !adminChecked ? (
            <LoadingScreen />
          ) : (isAdmin || isDepartmentAdmin) ? (
            <div className="flex flex-col h-screen">
              <TopBar profile={profile} />
              <AdminLayout />
            </div>
          ) : (
            <Navigate to="/" replace />
          )
        }
      >
        <Route index element={<Navigate to="settings" replace />} />
        <Route path="settings" element={<AdminPanel />} />
        {/* Users tab only for full admins */}
        <Route path="users" element={isAdmin ? <AdminUsers /> : <Navigate to="/admin/settings" replace />} />
      </Route>

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
        <Route path="tips/*" element={<TipsRoute />} />
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
    return <LoadingScreen />;
  }

  return (
    <SessionProvider>
      <AppContent />
    </SessionProvider>
  );
}

export default App;
