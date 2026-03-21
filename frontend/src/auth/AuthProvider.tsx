import { createContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
import { startLogin, handleCallback, parseJwtPayload, oidcConfig, type OidcTokens } from './oidc';
import { setTokenGetter } from '../api/client';
import { setWsTokenGetter, forgeWs } from '../api/websocket';

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
  const callbackProcessed = useRef(false);
  const wsConnected = useRef(false);

  // Handle callback on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');

    if (code && state) {
      // Guard against React strict mode double-invocation
      if (callbackProcessed.current) return;
      callbackProcessed.current = true;

      // We're on the callback - exchange code for tokens
      handleCallback(code, state)
        .then((tokens: OidcTokens) => {
          localStorage.setItem(TOKEN_KEY, tokens.idToken);
          setUser(getUserFromToken(tokens.idToken));
          setAuthError(null);
          // Clean URL
          window.history.replaceState({}, '', '/');
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
      // Token expired - clean up
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
    forgeWs.disconnect();
    wsConnected.current = false;
    const logoutUrl = `${oidcConfig.providerUrl}/logout?post_logout_redirect_uri=${encodeURIComponent(window.location.origin)}`;
    window.location.href = logoutUrl;
  }, []);

  const getToken = useCallback(async (): Promise<string | null> => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token || isTokenExpired(token)) {
      localStorage.removeItem(TOKEN_KEY);
      setUser(null);
      startLogin();
      return null;
    }
    return token;
  }, []);

  // Wire token getters for REST and WebSocket clients
  useEffect(() => {
    setTokenGetter(getToken);
    setWsTokenGetter(getToken);
  }, [getToken]);

  // Connect WebSocket when authenticated
  useEffect(() => {
    if (user && !wsConnected.current) {
      wsConnected.current = true;
      forgeWs.connect();
    }
    return () => {
      // Don't disconnect on unmount (strict mode) - only on sign out
    };
  }, [user]);

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
