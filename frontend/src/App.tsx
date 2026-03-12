import { useAuth } from './auth/useAuth';
import { LoginPage } from './auth/LoginPage';
import { SessionProvider } from './state/SessionContext';

function App() {
  const { isAuthenticated, isLoading, user } = useAuth();

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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Welcome, {user?.name}!</h1>
        </div>
      </div>
    </SessionProvider>
  );
}

export default App;
