// OIDC configuration for Digital Science ID
const OIDC_PROVIDER_URL = import.meta.env.VITE_OIDC_PROVIDER_URL || 'https://id-staging.digital-science.us';
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
