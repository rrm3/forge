import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { startLogin, handleCallback, parseJwtPayload, oidcConfig, type OidcTokens } from './oidc';
import { setTokenGetter } from '../api/client';
import { setChatTokenGetter } from '../api/chat';

interface AuthUser {
  userId: string;
  email: string;
  name: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  authError: string | null;
  user: AuthUser | null;
  signIn: () => void;
  signOut: () => void;
  getToken: () => Promise<string | null>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

const TOKEN_KEY = 'oidc_id_token';

function getUserFromToken(token: string): AuthUser {
  const payload = parseJwtPayload(token);
  return {
    userId: payload.sub as string,
    email: (payload.email as string) || '',
    name: (payload.name as string) || (payload.email as string) || '',
  };
}

function isTokenExpired(token: string): boolean {
  try {
    const payload = parseJwtPayload(token);
    const exp = payload.exp as number;
    return Date.now() >= exp * 1000;
  } catch {
    return true;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  // Handle callback on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');

    if (code && state) {
      // We're on the callback - exchange code for tokens
      handleCallback(code, state)
        .then((tokens: OidcTokens) => {
          localStorage.setItem(TOKEN_KEY, tokens.idToken);
          setUser(getUserFromToken(tokens.idToken));
          setAuthError(null);
          // Clean URL
          window.history.replaceState({}, '', window.location.pathname);
        })
        .catch((err) => {
          console.error('OIDC callback failed:', err);
          setAuthError(err instanceof Error ? err.message : 'Authentication failed');
        })
        .finally(() => setIsLoading(false));
      return;
    }

    // Check for existing token
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && !isTokenExpired(token)) {
      setUser(getUserFromToken(token));
    } else if (token) {
      // Token expired - clean up and redirect to login
      localStorage.removeItem(TOKEN_KEY);
    }
    setIsLoading(false);
  }, []);

  const signIn = useCallback(() => {
    setAuthError(null);
    startLogin();
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    // Redirect to IdP logout to end the session there too
    const logoutUrl = `${oidcConfig.providerUrl}/logout?redirect_uri=${encodeURIComponent(window.location.origin)}`;
    window.location.href = logoutUrl;
  }, []);

  const getToken = useCallback(async (): Promise<string | null> => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token || isTokenExpired(token)) {
      localStorage.removeItem(TOKEN_KEY);
      // Token expired - redirect to re-authenticate
      setUser(null);
      startLogin();
      return null;
    }
    return token;
  }, []);

  useEffect(() => {
    setTokenGetter(getToken);
    setChatTokenGetter(getToken);
  }, [getToken]);

  const value: AuthContextType = {
    isAuthenticated: user !== null,
    isLoading,
    authError,
    user,
    signIn,
    signOut,
    getToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
