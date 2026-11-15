/**
 * Browser sign-in with OpenID Connect (Authorization Code + PKCE, public client).
 * Works with Microsoft Entra ID (register the app as a "Single-page application"
 * with redirect URI <origin>/auth/callback) and any OIDC provider.
 * The ID token is verified by the Assay server, which then issues its own session.
 */
import api from './api';

export type SsoProvider = 'entra' | 'oidc';

interface Pending { provider: SsoProvider; issuer: string; clientId: string; verifier: string; state: string; nonce: string; tokenEndpoint: string }

const KEY = 'assay-sso-pending';

function random(bytes = 32): string {
    const a = new Uint8Array(bytes);
    crypto.getRandomValues(a);
    return btoa(String.fromCharCode(...a)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function challenge(verifier: string): Promise<string> {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
    return btoa(String.fromCharCode(...new Uint8Array(digest))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function discover(issuer: string) {
    const r = await fetch(`${issuer.replace(/\/$/, '')}/.well-known/openid-configuration`);
    if (!r.ok) throw new Error('Could not reach the sign-in provider');
    return r.json() as Promise<{ authorization_endpoint: string; token_endpoint: string }>;
}

export const redirectUri = () => `${window.location.origin}/auth/callback`;

export async function startSso(provider: SsoProvider, issuer: string, clientId: string): Promise<void> {
    const doc = await discover(issuer);
    const pending: Pending = { provider, issuer, clientId, verifier: random(48), state: random(16), nonce: random(16), tokenEndpoint: doc.token_endpoint };
    sessionStorage.setItem(KEY, JSON.stringify(pending));
    const url = new URL(doc.authorization_endpoint);
    url.search = new URLSearchParams({
        client_id: clientId, response_type: 'code', redirect_uri: redirectUri(), scope: 'openid email profile',
        state: pending.state, nonce: pending.nonce, code_challenge: await challenge(pending.verifier), code_challenge_method: 'S256',
    }).toString();
    window.location.assign(url.toString());
}

/** Finish on /auth/callback: check state, swap the code for an ID token, let the server verify it. */
export async function finishSso(params: URLSearchParams): Promise<string> {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    if (params.get('error')) throw new Error(params.get('error_description') || params.get('error') || 'Sign-in was cancelled');
    if (!raw) throw new Error('This sign-in link has expired. Start again.');
    const p = JSON.parse(raw) as Pending;
    if (params.get('state') !== p.state) throw new Error('Sign-in response did not match this browser. Start again.');
    const code = params.get('code');
    if (!code) throw new Error('No sign-in code returned');
    const r = await fetch(p.tokenEndpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ grant_type: 'authorization_code', code, redirect_uri: redirectUri(), client_id: p.clientId, code_verifier: p.verifier }),
    });
    const tokens = await r.json().catch(() => ({}));
    if (!r.ok || !tokens.id_token) throw new Error(tokens.error_description || 'The provider did not return an ID token');
    const session = await api.post('/auth/sso', { provider: p.provider, id_token: tokens.id_token, nonce: p.nonce });
    return session.data.access_token as string;
}
