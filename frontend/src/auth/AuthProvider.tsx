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
const REFRESH_LOCK_KEY = 'oidc_refresh_lock';

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

// Poll localStorage for a fresh token written by another tab's refresh
function waitForFreshToken(): Promise<OidcTokens> {
  return new Promise((resolve, reject) => {
    let remaining = 25; // 25 * 200ms = 5s max wait
    const poll = () => {
      const t = localStorage.getItem(TOKEN_KEY);
      if (t && !isTokenExpired(t)) {
        resolve({
          idToken: t,
          accessToken: '',
          refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) || '',
          expiresIn: getTokenExpiresIn(t) / 1000,
        });
        return;
      }
      if (--remaining <= 0) {
        reject(new Error('Cross-tab refresh timed out'));
        return;
      }
      setTimeout(poll, 200);
    };
    setTimeout(poll, 200);
  });
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
  // Refresh token present but no ID token - show loading while refresh is attempted
  if (localStorage.getItem(REFRESH_TOKEN_KEY)) {
    return { user: null, isLoading: true };
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
  const redirectingRef = useRef(false);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflightRefreshRef = useRef<Promise<OidcTokens> | null>(null);

  // Single entry point for token refresh. Deduplicates concurrent calls
  // within this tab AND coordinates across tabs via a localStorage lock
  // so that token rotation doesn't cause a losing tab to wipe shared state.
  const doRefresh = useCallback((): Promise<OidcTokens> => {
    if (inflightRefreshRef.current) return inflightRefreshRef.current;

    const rt = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!rt) return Promise.reject(new Error('No refresh token'));

    // Fast path: another tab may have just refreshed - check before doing work.
    // Only short-circuit if the token has plenty of time left. Don't skip the
    // proactive refresh that fires within the REFRESH_BUFFER_MS window.
    const existing = localStorage.getItem(TOKEN_KEY);
    if (existing && !isTokenExpired(existing) && getTokenExpiresIn(existing) > REFRESH_BUFFER_MS) {
      return Promise.resolve({
        idToken: existing, accessToken: '',
        refreshToken: rt, expiresIn: getTokenExpiresIn(existing) / 1000,
      } as OidcTokens);
    }

    // Cross-tab: if another tab is mid-refresh, wait for its result.
    // If the wait times out (lock-holder crashed or failed), try ourselves.
    const lockTs = parseInt(localStorage.getItem(REFRESH_LOCK_KEY) || '0', 10);
    if (Date.now() - lockTs < 10_000) {
      const promise = waitForFreshToken()
        .catch(() => {
          // Lock-holder failed or crashed. Claim the lock and try ourselves.
          localStorage.setItem(REFRESH_LOCK_KEY, String(Date.now()));
          return refreshWithToken(rt).then((tokens) => {
            localStorage.setItem(TOKEN_KEY, tokens.idToken);
            if (tokens.refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
            return tokens;
          }).catch((retryErr) => {
            const t = localStorage.getItem(TOKEN_KEY);
            if (t && !isTokenExpired(t)) {
              return { idToken: t, accessToken: '', refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) || '', expiresIn: getTokenExpiresIn(t) / 1000 } as OidcTokens;
            }
            throw retryErr;
          });
        })
        .finally(() => {
          localStorage.removeItem(REFRESH_LOCK_KEY);
          inflightRefreshRef.current = null;
        });
      inflightRefreshRef.current = promise;
      return promise;
    }

    // Claim the lock and send the refresh request
    localStorage.setItem(REFRESH_LOCK_KEY, String(Date.now()));

    const promise = refreshWithToken(rt)
      .then((tokens) => {
        // Persist tokens BEFORE releasing the lock so other tabs
        // see the new token when they check after the lock clears.
        localStorage.setItem(TOKEN_KEY, tokens.idToken);
        if (tokens.refreshToken) {
          localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
        }
        return tokens;
      })
      .catch((err) => {
        // Race lost: another tab may have rotated the token before us.
        // Re-check localStorage before propagating the failure.
        const t = localStorage.getItem(TOKEN_KEY);
        if (t && !isTokenExpired(t)) {
          return {
            idToken: t,
            accessToken: '',
            refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) || '',
            expiresIn: getTokenExpiresIn(t) / 1000,
          } as OidcTokens;
        }
        throw err;
      })
      .finally(() => {
        localStorage.removeItem(REFRESH_LOCK_KEY);
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
      if (redirectingRef.current) return null;
      redirectingRef.current = true;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      setUser(null);
      try {
        await startLogin();
      } catch {
        // startLogin failed (e.g., crypto.subtle unavailable) - reset so
        // future getToken calls can retry instead of being permanently stuck.
        redirectingRef.current = false;
      }
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

  // On mount: schedule refresh for valid tokens, or attempt refresh for expired ones.
  // Skip when an OIDC callback is in progress - the callback effect handles that.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('code') && params.get('state')) return;

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
    localStorage.removeItem(REFRESH_LOCK_KEY);
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
