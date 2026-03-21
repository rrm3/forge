import { createContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
import { startLogin, handleCallback, parseJwtPayload, silentRefresh, oidcConfig, type OidcTokens } from './oidc';
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

// Refresh 5 minutes before expiry
const REFRESH_BUFFER_MS = 5 * 60 * 1000;

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

function getTokenExpiresIn(token: string): number {
  try {
    const payload = parseJwtPayload(token);
    const exp = payload.exp as number;
    return exp * 1000 - Date.now();
  } catch {
    return 0;
  }
}

function getInitialAuthState(): { user: AuthUser | null; isLoading: boolean } {
  const params = new URLSearchParams(window.location.search);
  if (params.get('code') && params.get('state')) {
    return { user: null, isLoading: true };
  }

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
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Schedule a silent refresh before the token expires
  const scheduleRefresh = useCallback((token: string) => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }

    const expiresIn = getTokenExpiresIn(token);
    const refreshIn = Math.max(expiresIn - REFRESH_BUFFER_MS, 10000); // At least 10s from now

    console.log(`Token refresh scheduled in ${Math.round(refreshIn / 1000)}s`);

    refreshTimerRef.current = setTimeout(async () => {
      console.log('Attempting silent token refresh...');
      try {
        const tokens = await silentRefresh();
        localStorage.setItem(TOKEN_KEY, tokens.idToken);
        setUser(getUserFromToken(tokens.idToken));
        console.log('Silent refresh succeeded');
        // Schedule the next refresh
        scheduleRefresh(tokens.idToken);
      } catch (err) {
        console.warn('Silent refresh failed, will redirect on next API call:', err);
        // Don't force a redirect immediately - the user might still have a few
        // minutes left on the current token. The getToken() function will
        // redirect when the token actually expires.
      }
    }, refreshIn);
  }, []);

  // Handle OIDC callback on mount
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
          scheduleRefresh(tokens.idToken);
        })
        .catch((err) => {
          console.error('OIDC callback failed:', err);
          setAuthError(err instanceof Error ? err.message : 'Authentication failed');
        })
        .finally(() => setIsLoading(false));
    }
  }, [scheduleRefresh]);

  // Schedule refresh for existing token on mount
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && !isTokenExpired(token)) {
      scheduleRefresh(token);
    }
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, [scheduleRefresh]);

  const signIn = useCallback(() => {
    setAuthError(null);
    startLogin();
  }, []);

  const signOut = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }
    localStorage.removeItem(TOKEN_KEY);
    forgeWs.disconnect();
    wsConnected.current = false;
    const logoutUrl = `${oidcConfig.providerUrl}/logout?post_logout_redirect_uri=${encodeURIComponent(window.location.origin)}`;
    window.location.href = logoutUrl;
  }, []);

  const getToken = useCallback(async (): Promise<string | null> => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token || isTokenExpired(token)) {
      // Token is dead - try one silent refresh before redirecting
      try {
        const tokens = await silentRefresh();
        localStorage.setItem(TOKEN_KEY, tokens.idToken);
        setUser(getUserFromToken(tokens.idToken));
        scheduleRefresh(tokens.idToken);
        return tokens.idToken;
      } catch {
        // Silent refresh failed - full redirect
        localStorage.removeItem(TOKEN_KEY);
        setUser(null);
        startLogin();
        return null;
      }
    }
    return token;
  }, [scheduleRefresh]);

  // Wire token getters
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
