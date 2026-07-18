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

/**
 * Khởi tạo Authorization Code + PKCE ở chế độ check-sso: chỉ KIỂM TRA phiên,
 * không ép chuyển hướng. Người chưa đăng nhập được RequireAuth đưa về /login.
 */
export async function initializeAuthentication(): Promise<void> {
  if (useMockApi) return;

  const client = getKeycloak();
  await client.init({
    onLoad: 'check-sso',
    silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
    pkceMethod: 'S256',
    checkLoginIframe: false,
  });
}

/** Mock mode luôn coi là đã đăng nhập để demo giao diện không cần Keycloak. */
export function isAuthenticated(): boolean {
  if (useMockApi) return true;
  return keycloak?.authenticated === true;
}

/** Chuyển hướng sang Keycloak; sau khi đăng nhập quay lại đúng trang yêu cầu. */
export async function login(returnTo = '/'): Promise<void> {
  const client = getKeycloak();
  await client.login({ redirectUri: `${window.location.origin}${returnTo}` });
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
  await keycloak.logout({ redirectUri: `${window.location.origin}/login` });
}
