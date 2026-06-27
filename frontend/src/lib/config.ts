// Public runtime config. NEXT_PUBLIC_* values are inlined into the client bundle
// at build time; these are non-secret identifiers (Cognito pool/client IDs + API URL).
//
// IMPORTANT: each NEXT_PUBLIC_* var must be read via a *static* member access
// (process.env.NEXT_PUBLIC_FOO), not a dynamic key (process.env[key]). Webpack
// only inlines the statically-referenced names into the client bundle; a dynamic
// lookup resolves to undefined in the browser and silently falls back below.

function orFallback(value: string | undefined, fallback: string): string {
  return value && value.length > 0 ? value : fallback;
}

export const config = {
  apiBase: orFallback(
    process.env.NEXT_PUBLIC_API_BASE,
    "http://localhost:8000",
  ).replace(/\/$/, ""),
  cognito: {
    region: orFallback(process.env.NEXT_PUBLIC_COGNITO_REGION, "af-south-1"),
    userPoolId: orFallback(
      process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID,
      "af-south-1_xxxxxxxxx",
    ),
    clientId: orFallback(
      process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID,
      "local-client-id",
    ),
  },
  features: {
    // Demo-only "Simulate an inbound email" control. Defaults OFF so it never
    // ships in production builds; set NEXT_PUBLIC_ENABLE_SIMULATED_INTAKE=true
    // for local/demo environments. The /api/inbox endpoint itself is unaffected.
    simulatedIntake: process.env.NEXT_PUBLIC_ENABLE_SIMULATED_INTAKE === "true",
  },
} as const;
