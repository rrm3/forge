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

function getInitialAuthState(): { user: AuthUser | null; isLoading: boolean } {
  // Check for OIDC callback first
  const params = new URLSearchParams(window.location.search);
  if (params.get('code') && params.get('state')) {
    return { user: null, isLoading: true }; // Will handle in useEffect
  }

  // Synchronously check localStorage for existing token
  const token = localStorage.getItem(TOKEN_KEY);
  if (token && !isTokenExpired(token)) {
    return { user: getUserFromToken(token), isLoading: false };
  }
  if (token) {
    localStorage.removeItem(TOKEN_KEY);
  }
  return { user: null, isLoading: false };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const initialState = getInitialAuthState();
  const [user, setUser] = useState<AuthUser | null>(initialState.user);
  const [isLoading, setIsLoading] = useState(initialState.isLoading);
  const [authError, setAuthError] = useState<string | null>(null);
  const callbackProcessed = useRef(false);
  const wsConnected = useRef(false);

  // Handle OIDC callback on mount (only when code+state params are present)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');

    if (code && state) {
      if (callbackProcessed.current) return;
      callbackProcessed.current = true;

      handleCallback(code, state)
        .then((tokens: OidcTokens) => {
          localStorage.setItem(TOKEN_KEY, tokens.idToken);
          setUser(getUserFromToken(tokens.idToken));
          setAuthError(null);
          window.history.replaceState({}, '', '/');
        })
        .catch((err) => {
          console.error('OIDC callback failed:', err);
          setAuthError(err instanceof Error ? err.message : 'Authentication failed');
        })
        .finally(() => setIsLoading(false));
    }
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
