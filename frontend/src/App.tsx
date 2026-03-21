import { useEffect } from 'react';
import { useAuth } from './auth/useAuth';
import { SessionProvider } from './state/SessionContext';
import { useSession } from './state/SessionContext';
import { AppShell } from './components/AppShell';
import { SessionList } from './components/SessionList';
import { ChatView } from './components/ChatView';
import { HomeScreen } from './components/HomeScreen';
import { UserMenu } from './components/UserMenu';

function AppContent() {
  const { loadSessions } = useSession();
  const { state } = useSession();

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const sidebar = (
    <div className="flex flex-col h-full">
      <div className="flex-1 min-h-0">
        <SessionList />
      </div>
      <UserMenu />
    </div>
  );

  // Show home screen when no session is active
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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="w-full max-w-sm bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
          <p className="text-sm text-red-700 mb-4">{authError}</p>
          <button
            onClick={signIn}
            className="py-2 px-4 bg-gray-900 text-white text-sm font-medium rounded-md hover:bg-gray-700 transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-gray-300 border-t-gray-700 rounded-full animate-spin" />
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
