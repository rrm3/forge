import { useEffect } from 'react';
import { useAuth } from './auth/useAuth';
import { LoginPage } from './auth/LoginPage';
import { SessionProvider } from './state/SessionContext';
import { useSession } from './state/SessionContext';
import { AppShell } from './components/AppShell';
import { SessionList } from './components/SessionList';
import { ChatView } from './components/ChatView';
import { UserMenu } from './components/UserMenu';

function AppContent() {
  const { loadSessions } = useSession();

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

  return <AppShell sidebar={sidebar} content={<ChatView />} />;
}

function App() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-gray-300 border-t-gray-700 rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <SessionProvider>
      <AppContent />
    </SessionProvider>
  );
}

export default App;
