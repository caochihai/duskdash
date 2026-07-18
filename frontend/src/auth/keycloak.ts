import Keycloak, { type KeycloakTokenParsed } from 'keycloak-js';

const useMockApi = import.meta.env.VITE_USE_MOCK_API !== 'false';

let keycloak: Keycloak | null = null;

function getKeycloak(): Keycloak {
  if (!keycloak) {
    keycloak = new Keycloak({
      url: import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8080',
      realm: import.meta.env.VITE_KEYCLOAK_REALM || 'bank-ai',
      clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'bank-ai-frontend',
    });
  }
  return keycloak;
}

/** Initialize Authorization Code + PKCE before protected API queries run. */
export async function initializeAuthentication(): Promise<void> {
  if (useMockApi) return;

  const client = getKeycloak();
  const authenticated = await client.init({
    onLoad: 'login-required',
    pkceMethod: 'S256',
    checkLoginIframe: false,
  });

  if (!authenticated) await client.login();
}

/** Return a short-lived in-memory token; tokens are never written to browser storage. */
export async function getValidAccessToken(): Promise<string | null> {
  if (useMockApi) return null;

  const client = getKeycloak();
  if (!client.authenticated) return null;
  await client.updateToken(30);
  return client.token ?? null;
}

export function getAuthenticatedClaims(): KeycloakTokenParsed | undefined {
  return keycloak?.tokenParsed;
}

export async function logout(): Promise<void> {
  if (!keycloak) return;
  await keycloak.logout({ redirectUri: window.location.origin });
}
