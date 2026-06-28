/**
 * Post-deploy smoke test for the STAK (Sectional Title Agent Platform) live system.
 *
 * REAL HTTP ONLY — there is no mocking here. Every assertion talks to the
 * actually-deployed API Gateway -> Lambda (FastAPI) and CloudFront origin.
 *
 * It exists to catch the exact class of bug we just hit: a CORS preflight
 * (HTTP OPTIONS) returning 400 "Disallowed CORS origin", which silently breaks
 * every browser call from the dashboard. A green unit-test suite never catches
 * that because it only shows up against the real gateway config.
 *
 * Run:  cd tests/smoke && npm install && npm run smoke
 *
 * Mandatory checks (exit non-zero on failure):
 *   1. GET  {API}/api/health                     -> 200, JSON status === "ok"
 *   2. OPTIONS preflight for /api/documents       -> 2xx + ACAO header (NOT 400)
 *   3. OPTIONS preflight for /api/documents/upload-url -> 2xx + ACAO header (NOT 400)
 *   4. GET  {API}/api/documents (no auth)         -> 401 (route exists, auth enforced)
 *
 * Optional check (SKIPPED unless SMOKE_USERNAME && SMOKE_PASSWORD are set):
 *   5. Authenticated round-trip: Cognito login -> GET /api/documents (200)
 *      -> POST /api/documents/upload-url (200 + uploadUrl) -> PUT bytes to S3 (200/204)
 */

import {
  CognitoIdentityProviderClient,
  InitiateAuthCommand,
} from "@aws-sdk/client-cognito-identity-provider";

// ── Config (env with live defaults) ─────────────────────────────────────────
const API_BASE = (
  process.env.SMOKE_API_BASE ??
  "https://f29y0n9h2d.execute-api.af-south-1.amazonaws.com"
).replace(/\/+$/, "");
const ORIGIN = (
  process.env.SMOKE_ORIGIN ?? "https://d2vcnwv2hywkdo.cloudfront.net"
).replace(/\/+$/, "");
const COGNITO_REGION = process.env.SMOKE_COGNITO_REGION ?? "af-south-1";
const COGNITO_CLIENT_ID =
  process.env.SMOKE_COGNITO_CLIENT_ID ?? "1g4ori9ppoc432omgiu6s7efsa";
const USERNAME = process.env.SMOKE_USERNAME;
const PASSWORD = process.env.SMOKE_PASSWORD;

// ── Tiny result tracker ──────────────────────────────────────────────────────
type Outcome = "PASS" | "FAIL" | "SKIP";
interface Result {
  name: string;
  outcome: Outcome;
  detail: string;
}
const results: Result[] = [];

function record(name: string, outcome: Outcome, detail: string): void {
  results.push({ name, outcome, detail });
  const tag =
    outcome === "PASS" ? "PASS" : outcome === "SKIP" ? "SKIP" : "FAIL";
  console.log(`[${tag}] ${name} — ${detail}`);
}

async function mandatory(
  name: string,
  fn: () => Promise<string>,
): Promise<void> {
  try {
    const detail = await fn();
    record(name, "PASS", detail);
  } catch (err) {
    record(name, "FAIL", err instanceof Error ? err.message : String(err));
  }
}

function assert(cond: boolean, message: string): void {
  if (!cond) throw new Error(message);
}

// ── Check 1: health ──────────────────────────────────────────────────────────
async function checkHealth(): Promise<string> {
  const url = `${API_BASE}/api/health`;
  const res = await fetch(url, { method: "GET" });
  assert(res.status === 200, `expected 200 from ${url}, got ${res.status}`);
  const body = (await res.json()) as { status?: string };
  assert(
    body.status === "ok",
    `expected JSON status "ok" from ${url}, got ${JSON.stringify(body)}`,
  );
  return `${url} -> 200, status="ok"`;
}

// ── Check 2/3: CORS preflight regression ─────────────────────────────────────
async function checkPreflight(path: string, method: string): Promise<string> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: "OPTIONS",
    headers: {
      Origin: ORIGIN,
      "Access-Control-Request-Method": method,
      "Access-Control-Request-Headers": "authorization,content-type",
    },
  });
  const acao = res.headers.get("access-control-allow-origin");

  // The specific regression: gateway/Lambda rejects the preflight with 400
  // "Disallowed CORS origin". Name the endpoint loudly so failures are obvious.
  assert(
    res.status !== 400,
    `CORS preflight for ${method} ${path} returned 400 (likely "Disallowed CORS origin"). ` +
      `Origin=${ORIGIN}. The browser cannot call this endpoint until CORS is fixed.`,
  );
  assert(
    res.status === 200 || res.status === 204,
    `CORS preflight for ${method} ${path} expected 200/204, got ${res.status}`,
  );
  assert(
    acao !== null,
    `CORS preflight for ${method} ${path} is missing the access-control-allow-origin header`,
  );
  assert(
    acao === "*" || acao === ORIGIN,
    `CORS preflight for ${method} ${path} returned access-control-allow-origin="${acao}", ` +
      `expected "*" or "${ORIGIN}"`,
  );
  return `OPTIONS ${path} -> ${res.status}, access-control-allow-origin="${acao}"`;
}

// ── Check 4: unauthenticated route is protected ──────────────────────────────
async function checkUnauthorized(): Promise<string> {
  const url = `${API_BASE}/api/documents`;
  const res = await fetch(url, { method: "GET" });
  assert(
    res.status === 401,
    `expected 401 (no Authorization header) from ${url}, got ${res.status}`,
  );
  return `GET /api/documents (no auth) -> 401`;
}

// ── Check 5 (optional): authenticated round-trip ─────────────────────────────
async function getAccessToken(): Promise<string | null> {
  const client = new CognitoIdentityProviderClient({ region: COGNITO_REGION });
  try {
    const out = await client.send(
      new InitiateAuthCommand({
        AuthFlow: "USER_PASSWORD_AUTH",
        ClientId: COGNITO_CLIENT_ID,
        AuthParameters: { USERNAME: USERNAME!, PASSWORD: PASSWORD! },
      }),
    );
    const token = out.AuthenticationResult?.AccessToken;
    return token ?? null;
  } catch (err) {
    // USER_PASSWORD_AUTH may not be enabled on the app client — skip gracefully.
    const msg = err instanceof Error ? err.message : String(err);
    console.log(
      `[note] Cognito USER_PASSWORD_AUTH unavailable (${msg}). ` +
        `Skipping authenticated round-trip.`,
    );
    return null;
  }
}

async function checkAuthenticatedRoundTrip(): Promise<void> {
  if (!USERNAME || !PASSWORD) {
    record(
      "auth round-trip",
      "SKIP",
      "SMOKE_USERNAME / SMOKE_PASSWORD not set",
    );
    return;
  }

  let token: string | null;
  try {
    token = await getAccessToken();
  } catch (err) {
    record(
      "auth round-trip",
      "SKIP",
      `auth error: ${err instanceof Error ? err.message : String(err)}`,
    );
    return;
  }

  if (!token) {
    record(
      "auth round-trip",
      "SKIP",
      "could not obtain access token (USER_PASSWORD_AUTH likely disabled)",
    );
    return;
  }

  const authHeaders = {
    Authorization: `Bearer ${token}`,
    Origin: ORIGIN,
  };

  try {
    // 5a. GET /api/documents -> 200
    const listRes = await fetch(`${API_BASE}/api/documents`, {
      method: "GET",
      headers: authHeaders,
    });
    assert(
      listRes.status === 200,
      `authenticated GET /api/documents expected 200, got ${listRes.status}`,
    );

    // 5b. POST /api/documents/upload-url -> 200 + uploadUrl
    const uploadUrlRes = await fetch(`${API_BASE}/api/documents/upload-url`, {
      method: "POST",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: "smoke-test.txt",
        contentType: "text/plain",
      }),
    });
    assert(
      uploadUrlRes.status === 200,
      `POST /api/documents/upload-url expected 200, got ${uploadUrlRes.status}`,
    );
    const uploadBody = (await uploadUrlRes.json()) as { uploadUrl?: string };
    assert(
      typeof uploadBody.uploadUrl === "string" &&
        uploadBody.uploadUrl.length > 0,
      `POST /api/documents/upload-url response missing uploadUrl: ${JSON.stringify(
        uploadBody,
      )}`,
    );

    // 5c. PUT bytes to the presigned S3 URL -> 200/204
    const putRes = await fetch(uploadBody.uploadUrl!, {
      method: "PUT",
      headers: { "Content-Type": "text/plain" },
      body: "smoke-test bytes\n",
    });
    assert(
      putRes.status === 200 || putRes.status === 204,
      `PUT to presigned uploadUrl expected 200/204, got ${putRes.status}`,
    );

    record(
      "auth round-trip",
      "PASS",
      "login -> GET /api/documents (200) -> upload-url (200) -> S3 PUT (2xx)",
    );
  } catch (err) {
    record(
      "auth round-trip",
      "FAIL",
      err instanceof Error ? err.message : String(err),
    );
  }
}

// ── Runner ───────────────────────────────────────────────────────────────────
async function main(): Promise<void> {
  console.log("STAK post-deploy smoke test (REAL HTTP, no mocks)");
  console.log(`  API_BASE = ${API_BASE}`);
  console.log(`  ORIGIN   = ${ORIGIN}`);
  console.log("");

  // Mandatory checks.
  await mandatory("health", checkHealth);
  await mandatory("CORS preflight /api/documents", () =>
    checkPreflight("/api/documents", "GET"),
  );
  await mandatory("CORS preflight /api/documents/upload-url", () =>
    checkPreflight("/api/documents/upload-url", "POST"),
  );
  await mandatory("unauthorized /api/documents", checkUnauthorized);

  // Optional check — never fails the run when prerequisites are absent.
  await checkAuthenticatedRoundTrip();

  // Summary.
  console.log("");
  console.log("── Summary ─────────────────────────────────────────────");
  for (const r of results) {
    console.log(`  ${r.outcome.padEnd(4)}  ${r.name}`);
  }
  const failed = results.filter((r) => r.outcome === "FAIL");
  const passed = results.filter((r) => r.outcome === "PASS").length;
  const skipped = results.filter((r) => r.outcome === "SKIP").length;
  console.log(
    `  ${passed} passed, ${failed.length} failed, ${skipped} skipped`,
  );
  console.log("────────────────────────────────────────────────────────");

  if (failed.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error("Smoke test crashed:", err);
  process.exitCode = 1;
});
