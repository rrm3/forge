import { createContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
import { startLogin, handleCallback, parseJwtPayload, refreshWithToken, oidcConfig, type OidcTokens } from './oidc';
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
const REFRESH_TOKEN_KEY = 'oidc_refresh_token';

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
  // ID token expired but we might have a refresh token - show loading
  // while getToken() attempts to refresh on first call
  if (token && localStorage.getItem(REFRESH_TOKEN_KEY)) {
    return { user: null, isLoading: true };
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
  const signingOutRef = useRef(false);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflightRefreshRef = useRef<Promise<OidcTokens> | null>(null);

  // Single entry point for token refresh. Deduplicates concurrent calls
  // so that token rotation doesn't cause the second caller to fail.
  const doRefresh = useCallback((): Promise<OidcTokens> => {
    if (inflightRefreshRef.current) return inflightRefreshRef.current;

    const rt = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!rt) return Promise.reject(new Error('No refresh token'));

    const promise = refreshWithToken(rt).finally(() => {
      inflightRefreshRef.current = null;
    });
    inflightRefreshRef.current = promise;
    return promise;
  }, []);

  // Apply a successful refresh result to state + localStorage
  const applyRefresh = useCallback((tokens: OidcTokens) => {
    localStorage.setItem(TOKEN_KEY, tokens.idToken);
    if (tokens.refreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
    }
    setUser(getUserFromToken(tokens.idToken));
    return tokens.idToken;
  }, []);

  // Schedule a proactive refresh before the ID token expires
  const scheduleRefresh = useCallback((token: string) => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }

    const expiresIn = getTokenExpiresIn(token);
    const refreshIn = Math.max(expiresIn - REFRESH_BUFFER_MS, 10000);

    refreshTimerRef.current = setTimeout(async () => {
      try {
        const tokens = await doRefresh();
        applyRefresh(tokens);
        scheduleRefresh(tokens.idToken);
      } catch {
        // Refresh failed. getToken() will handle redirect on next API call.
      }
    }, refreshIn);
  }, [doRefresh, applyRefresh]);

  // getToken: the authoritative way to get a valid token.
  // Returns cached token if valid, refreshes if expired, redirects if both dead.
  const getToken = useCallback(async (): Promise<string | null> => {
    if (signingOutRef.current) return null;

    const token = localStorage.getItem(TOKEN_KEY);
    if (token && !isTokenExpired(token)) return token;

    try {
      const tokens = await doRefresh();
      const idToken = applyRefresh(tokens);
      scheduleRefresh(idToken);
      return idToken;
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      setUser(null);
      startLogin();
      return null;
    }
  }, [doRefresh, applyRefresh, scheduleRefresh]);

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
          applyRefresh(tokens);
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
  }, [applyRefresh, scheduleRefresh]);

  // On mount: schedule refresh for valid tokens, or attempt refresh for expired ones
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && !isTokenExpired(token)) {
      scheduleRefresh(token);
    } else if (localStorage.getItem(REFRESH_TOKEN_KEY)) {
      // Expired ID token + refresh token: use getToken() to refresh
      getToken().finally(() => setIsLoading(false));
    }
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, [getToken, scheduleRefresh]);

  const signIn = useCallback(() => {
    setAuthError(null);
    startLogin();
  }, []);

  const signOut = useCallback(() => {
    signingOutRef.current = true;
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    forgeWs.disconnect();
    wsConnected.current = false;
    const logoutUrl = `${oidcConfig.providerUrl}/logout?post_logout_redirect_uri=${encodeURIComponent(window.location.origin)}`;
    window.location.href = logoutUrl;
  }, []);

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
