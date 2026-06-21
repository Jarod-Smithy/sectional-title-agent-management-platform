"use client";

import { useMemo } from "react";
import { ApiClient } from "./api";
import { useAuth } from "./auth";

/** Returns an ApiClient bound to the current session's bearer token. */
export function useApi(): ApiClient {
  const { getToken } = useAuth();
  return useMemo(() => new ApiClient(getToken), [getToken]);
}
