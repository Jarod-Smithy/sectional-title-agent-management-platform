"use client";

import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserPool,
  type CognitoUserSession,
} from "amazon-cognito-identity-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { config } from "./config";

/**
 * Outcome of {@link AuthState.signIn}. `NEW_PASSWORD_REQUIRED` means the user was
 * created by an administrator (or had their password reset) and must choose a
 * permanent password before the session is established — the UI should then call
 * {@link AuthState.completeNewPassword}.
 */
export type SignInResult = "SIGNED_IN" | "NEW_PASSWORD_REQUIRED";

export interface AuthState {
  email: string | null;
  ready: boolean;
  isAuthenticated: boolean;
  /**
   * Starts USER_SRP_AUTH. Resolves with `SIGNED_IN` once a session is active, or
   * `NEW_PASSWORD_REQUIRED` when a first-sign-in password must be set.
   */
  signIn: (email: string, password: string) => Promise<SignInResult>;
  /**
   * Completes a `NEW_PASSWORD_REQUIRED` challenge raised by the most recent
   * {@link AuthState.signIn}. Resolves once the session is established.
   */
  completeNewPassword: (newPassword: string) => Promise<void>;
  /** Sends a password-reset verification code to the user's email. */
  forgotPassword: (email: string) => Promise<void>;
  /** Confirms a password reset using the emailed code and a new password. */
  confirmForgotPassword: (
    email: string,
    code: string,
    newPassword: string,
  ) => Promise<void>;
  signOut: () => void;
  /** Synchronous accessor used by the API client to attach the bearer token. */
  getToken: () => string | null;
}

interface PendingPasswordChallenge {
  user: CognitoUser;
  requiredAttributes: string[];
}

/** Refresh the access token this many ms before it actually expires. */
const REFRESH_SKEW_MS = 5 * 60 * 1000;

const AuthContext = createContext<AuthState | null>(null);

function newPool(): CognitoUserPool {
  return new CognitoUserPool({
    UserPoolId: config.cognito.userPoolId,
    ClientId: config.cognito.clientId,
  });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  // Token is held in a ref so the API client can read it synchronously without
  // re-rendering on every request.
  const tokenRef = useRef<string | null>(null);
  // The authenticated CognitoUser, kept so we can proactively refresh its tokens.
  const userRef = useRef<CognitoUser | null>(null);
  // Pending timer that refreshes the session shortly before the token expires.
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The CognitoUser awaiting a `completeNewPassword` call after a first sign-in.
  const challengeRef = useRef<PendingPasswordChallenge | null>(null);
  // Indirection so the scheduled timer always invokes the latest refresh closure.
  const refreshRef = useRef<(user: CognitoUser) => void>(() => {});

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current !== null) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  const clearSession = useCallback(() => {
    clearRefreshTimer();
    tokenRef.current = null;
    userRef.current = null;
    setEmail(null);
  }, [clearRefreshTimer]);

  const applySession = useCallback(
    (user: CognitoUser, session: CognitoUserSession) => {
      userRef.current = user;
      tokenRef.current = session.getAccessToken().getJwtToken();
      const payload = session.getIdToken().decodePayload() as {
        email?: string;
      };
      setEmail(payload.email ?? null);

      // Schedule a proactive refresh so an idle session never silently expires.
      clearRefreshTimer();
      const expiresAtMs = session.getAccessToken().getExpiration() * 1000;
      const delay = Math.max(expiresAtMs - Date.now() - REFRESH_SKEW_MS, 0);
      refreshTimerRef.current = setTimeout(() => {
        refreshRef.current(user);
      }, delay);
    },
    [clearRefreshTimer],
  );

  const refreshSession = useCallback(
    (user: CognitoUser) => {
      // getSession transparently swaps in a fresh access/id token using the
      // cached refresh token; refreshSession then guarantees rotated tokens.
      user.getSession(
        (err: Error | null, session: CognitoUserSession | null) => {
          if (err || !session) {
            clearSession();
            return;
          }
          user.refreshSession(
            session.getRefreshToken(),
            (refreshErr?: Error, newSession?: CognitoUserSession) => {
              if (refreshErr || !newSession) {
                clearSession();
                return;
              }
              applySession(user, newSession);
            },
          );
        },
      );
    },
    [applySession, clearSession],
  );

  useEffect(() => {
    refreshRef.current = refreshSession;
  }, [refreshSession]);

  // Tear down any pending refresh timer when the provider unmounts.
  useEffect(() => clearRefreshTimer, [clearRefreshTimer]);

  // Restore an existing session on first load.
  useEffect(() => {
    const pool = newPool();
    const current = pool.getCurrentUser();
    if (!current) {
      setReady(true);
      return;
    }
    current.getSession(
      (err: Error | null, session: CognitoUserSession | null) => {
        if (!err && session && session.isValid()) {
          applySession(current, session);
        } else {
          clearSession();
        }
        setReady(true);
      },
    );
  }, [applySession, clearSession]);

  const signIn = useCallback(
    (userEmail: string, password: string) =>
      new Promise<SignInResult>((resolve, reject) => {
        const user = new CognitoUser({ Username: userEmail, Pool: newPool() });
        const details = new AuthenticationDetails({
          Username: userEmail,
          Password: password,
        });
        user.authenticateUser(details, {
          onSuccess: (session) => {
            challengeRef.current = null;
            applySession(user, session);
            resolve("SIGNED_IN");
          },
          onFailure: (err) => reject(err as Error),
          // Admin-invited trustees (or post-reset users) must set a permanent
          // password before the session is issued. Stash the challenge so the
          // UI can finish it via `completeNewPassword`.
          newPasswordRequired: (
            _userAttributes: Record<string, string>,
            requiredAttributes: string[],
          ) => {
            challengeRef.current = {
              user,
              requiredAttributes: requiredAttributes ?? [],
            };
            resolve("NEW_PASSWORD_REQUIRED");
          },
        });
      }),
    [applySession],
  );

  const completeNewPassword = useCallback(
    (newPassword: string) =>
      new Promise<void>((resolve, reject) => {
        const pending = challengeRef.current;
        if (!pending) {
          reject(
            new Error(
              "No password setup is in progress. Please sign in again.",
            ),
          );
          return;
        }
        // We only collect a password in this flow; admin-created accounts have
        // their other required attributes (e.g. email) pre-populated, so an
        // empty attribute map is the correct payload here.
        const noExtraAttributes: Record<string, string> = {};
        pending.user.completeNewPasswordChallenge(
          newPassword,
          noExtraAttributes,
          {
            onSuccess: (session) => {
              challengeRef.current = null;
              applySession(pending.user, session);
              resolve();
            },
            onFailure: (err) => reject(err as Error),
          },
        );
      }),
    [applySession],
  );

  const forgotPassword = useCallback(
    (userEmail: string) =>
      new Promise<void>((resolve, reject) => {
        const user = new CognitoUser({ Username: userEmail, Pool: newPool() });
        user.forgotPassword({
          // Called once Cognito has dispatched the verification code.
          onSuccess: () => resolve(),
          onFailure: (err: Error) => reject(err),
        });
      }),
    [],
  );

  const confirmForgotPassword = useCallback(
    (userEmail: string, code: string, newPassword: string) =>
      new Promise<void>((resolve, reject) => {
        const user = new CognitoUser({ Username: userEmail, Pool: newPool() });
        user.confirmPassword(code, newPassword, {
          onSuccess: () => resolve(),
          onFailure: (err: Error) => reject(err),
        });
      }),
    [],
  );

  const signOut = useCallback(() => {
    const current = newPool().getCurrentUser();
    current?.signOut();
    challengeRef.current = null;
    clearSession();
  }, [clearSession]);

  const getToken = useCallback(() => tokenRef.current, []);

  const value = useMemo<AuthState>(
    () => ({
      email,
      ready,
      isAuthenticated: email !== null,
      signIn,
      completeNewPassword,
      forgotPassword,
      confirmForgotPassword,
      signOut,
      getToken,
    }),
    [
      email,
      ready,
      signIn,
      completeNewPassword,
      forgotPassword,
      confirmForgotPassword,
      signOut,
      getToken,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
