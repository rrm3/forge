import { useAuth } from './useAuth';

export function LoginPage() {
  const { signIn, authError } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <div className="mb-8 text-center">
            <h1 className="text-2xl font-semibold text-gray-900">AI Tuesdays</h1>
            <p className="mt-1 text-sm text-gray-500">Digital Science Forge</p>
          </div>

          {authError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-700">{authError}</p>
            </div>
          )}

          <button
            onClick={signIn}
            className="w-full py-2 px-4 bg-gray-900 text-white text-sm font-medium rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
          >
            Sign in with Digital Science ID
          </button>
        </div>
      </div>
    </div>
  );
}
