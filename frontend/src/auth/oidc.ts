// OIDC configuration for Digital Science ID
const OIDC_PROVIDER_URL = import.meta.env.VITE_OIDC_PROVIDER_URL || 'https://id.digitalscience.ai';
const OIDC_CLIENT_ID = import.meta.env.VITE_OIDC_CLIENT_ID || '';
const OIDC_REDIRECT_URI = import.meta.env.VITE_OIDC_REDIRECT_URI || `${window.location.origin}/callback`;

export const oidcConfig = {
  providerUrl: OIDC_PROVIDER_URL,
  clientId: OIDC_CLIENT_ID,
  redirectUri: OIDC_REDIRECT_URI,
  scopes: 'openid email profile',
};

// PKCE helpers
function generateRandomString(length: number): string {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('').slice(0, length);
}

async function sha256(plain: string): Promise<ArrayBuffer> {
  const encoder = new TextEncoder();
  return crypto.subtle.digest('SHA-256', encoder.encode(plain));
}

function base64urlEncode(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export async function startLogin(): Promise<void> {
  const codeVerifier = generateRandomString(64);
  const codeChallenge = base64urlEncode(await sha256(codeVerifier));
  const state = generateRandomString(32);

  // Store for callback
  sessionStorage.setItem('oidc_code_verifier', codeVerifier);
  sessionStorage.setItem('oidc_state', state);

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: oidcConfig.clientId,
    redirect_uri: oidcConfig.redirectUri,
    scope: oidcConfig.scopes,
    state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  });

  window.location.href = `${oidcConfig.providerUrl}/authorize?${params}`;
}

export interface OidcTokens {
  idToken: string;
  accessToken: string;
  expiresIn: number;
}

export async function handleCallback(code: string, state: string): Promise<OidcTokens> {
  const savedState = sessionStorage.getItem('oidc_state');
  const codeVerifier = sessionStorage.getItem('oidc_code_verifier');

  // Clean up
  sessionStorage.removeItem('oidc_state');
  sessionStorage.removeItem('oidc_code_verifier');

  if (!savedState || state !== savedState) {
    throw new Error('Invalid state parameter');
  }

  if (!codeVerifier) {
    throw new Error('Missing code verifier');
  }

  const response = await fetch(`${oidcConfig.providerUrl}/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      redirect_uri: oidcConfig.redirectUri,
      client_id: oidcConfig.clientId,
      code_verifier: codeVerifier,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error_description || error.error || 'Token exchange failed');
  }

  const data = await response.json();
  return {
    idToken: data.id_token,
    accessToken: data.access_token,
    expiresIn: data.expires_in,
  };
}

export function parseJwtPayload(token: string): Record<string, unknown> {
  const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
  return JSON.parse(atob(base64));
}

/**
 * Silent token refresh via hidden iframe.
 *
 * Sends the user to the OIDC authorize endpoint with prompt=none in a
 * hidden iframe. If the provider's session is still alive, it redirects
 * back with a new auth code which we exchange for fresh tokens.
 * If the session is dead, the iframe returns an error and we fall back
 * to a full redirect.
 */
export async function silentRefresh(): Promise<OidcTokens> {
  const codeVerifier = generateRandomString(64);
  const codeChallenge = base64urlEncode(await sha256(codeVerifier));
  const state = generateRandomString(32);

  // Use a dedicated silent callback path
  const silentRedirectUri = `${window.location.origin}/silent-callback.html`;

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: oidcConfig.clientId,
    redirect_uri: silentRedirectUri,
    scope: oidcConfig.scopes,
    state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
    prompt: 'none',
  });

  const authorizeUrl = `${oidcConfig.providerUrl}/authorize?${params}`;

  return new Promise<OidcTokens>((resolve, reject) => {
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    document.body.appendChild(iframe);

    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error('Silent refresh timed out'));
    }, 10000);

    function cleanup() {
      clearTimeout(timeout);
      window.removeEventListener('message', onMessage);
      if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
    }

    function onMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      if (event.data?.type !== 'silent-callback') return;

      cleanup();

      const { code: cbCode, state: cbState, error } = event.data;

      if (error) {
        reject(new Error(error));
        return;
      }

      if (cbState !== state) {
        reject(new Error('State mismatch in silent refresh'));
        return;
      }

      // Exchange code for tokens
      fetch(`${oidcConfig.providerUrl}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'authorization_code',
          code: cbCode,
          redirect_uri: silentRedirectUri,
          client_id: oidcConfig.clientId,
          code_verifier: codeVerifier,
        }),
      })
        .then(async (resp) => {
          if (!resp.ok) throw new Error('Token exchange failed');
          const data = await resp.json();
          resolve({
            idToken: data.id_token,
            accessToken: data.access_token,
            expiresIn: data.expires_in,
          });
        })
        .catch(reject);
    }

    window.addEventListener('message', onMessage);
    iframe.src = authorizeUrl;
  });
}
