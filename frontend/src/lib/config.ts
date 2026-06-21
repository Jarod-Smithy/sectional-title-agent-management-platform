// Public runtime config. NEXT_PUBLIC_* values are inlined into the client bundle
// at build time; these are non-secret identifiers (Cognito pool/client IDs + API URL).

function env(key: string, fallback: string): string {
  const value = process.env[key];
  return value && value.length > 0 ? value : fallback;
}

export const config = {
  apiBase: env("NEXT_PUBLIC_API_BASE", "http://localhost:8000").replace(
    /\/$/,
    "",
  ),
  cognito: {
    region: env("NEXT_PUBLIC_COGNITO_REGION", "af-south-1"),
    userPoolId: env("NEXT_PUBLIC_COGNITO_USER_POOL_ID", "af-south-1_xxxxxxxxx"),
    clientId: env("NEXT_PUBLIC_COGNITO_CLIENT_ID", "local-client-id"),
  },
} as const;
