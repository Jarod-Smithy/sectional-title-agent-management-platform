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

export interface AuthState {
  email: string | null;
  ready: boolean;
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
  /** Synchronous accessor used by the API client to attach the bearer token. */
  getToken: () => string | null;
}

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

  const applySession = useCallback((session: CognitoUserSession) => {
    tokenRef.current = session.getAccessToken().getJwtToken();
    const payload = session.getIdToken().decodePayload() as { email?: string };
    setEmail(payload.email ?? null);
  }, []);

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
          applySession(session);
        } else {
          tokenRef.current = null;
          setEmail(null);
        }
        setReady(true);
      },
    );
  }, [applySession]);

  const signIn = useCallback(
    (userEmail: string, password: string) =>
      new Promise<void>((resolve, reject) => {
        const user = new CognitoUser({ Username: userEmail, Pool: newPool() });
        const details = new AuthenticationDetails({
          Username: userEmail,
          Password: password,
        });
        user.authenticateUser(details, {
          onSuccess: (session) => {
            applySession(session);
            resolve();
          },
          onFailure: (err) => reject(err as Error),
          newPasswordRequired: () =>
            reject(
              new Error(
                "A permanent password is required. Ask an administrator to reset your account.",
              ),
            ),
        });
      }),
    [applySession],
  );

  const signOut = useCallback(() => {
    const current = newPool().getCurrentUser();
    current?.signOut();
    tokenRef.current = null;
    setEmail(null);
  }, []);

  const getToken = useCallback(() => tokenRef.current, []);

  const value = useMemo<AuthState>(
    () => ({
      email,
      ready,
      isAuthenticated: email !== null,
      signIn,
      signOut,
      getToken,
    }),
    [email, ready, signIn, signOut, getToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
