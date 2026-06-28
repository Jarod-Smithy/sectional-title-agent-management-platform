import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  FALLBACK_COPY,
  NOTIFIED_COPY,
  isConnectivityError,
  isReportableError,
  reportAndNotify,
  resetReportedSignatures,
} from "./errorReporting";
import { ApiError } from "./api";
import type { BugReportIn, IssueCreatedOut } from "./types";

/** Stubs only the network boundary (api.reportBug) and records the payload. */
function makeApi(result: IssueCreatedOut | Error) {
  let lastPayload: BugReportIn | undefined;
  const reportBug = vi.fn((payload: BugReportIn) => {
    lastPayload = payload;
    return result instanceof Error
      ? Promise.reject(result)
      : Promise.resolve(result);
  });
  return { reportBug, lastPayload: () => lastPayload };
}

describe("reportAndNotify", () => {
  beforeEach(() => resetReportedSignatures());

  it("notifies with a tracking link when an issue is created", async () => {
    const api = makeApi({
      number: 42,
      url: "https://github.com/acme/repo/issues/42",
      created: true,
    });
    const notify = vi.fn();

    await reportAndNotify({
      error: new Error("boom"),
      context: "ctx.a",
      api,
      notify,
    });

    expect(api.reportBug).toHaveBeenCalledOnce();
    expect(notify).toHaveBeenCalledTimes(1);
    const arg = notify.mock.calls[0]?.[0];
    expect(arg?.severity).toBe("error");
    expect(arg?.message).toBe(NOTIFIED_COPY);
    expect(arg?.action).toEqual({
      label: "Track issue #42",
      href: "https://github.com/acme/repo/issues/42",
    });
  });

  it("falls back with no link when the tracker is offline (created:false)", async () => {
    const api = makeApi({ number: 0, url: "log:not-created", created: false });
    const notify = vi.fn();

    await reportAndNotify({
      error: new Error("boom"),
      context: "ctx.b",
      api,
      notify,
    });

    expect(api.reportBug).toHaveBeenCalledOnce();
    const arg = notify.mock.calls[0]?.[0];
    expect(arg?.message).toBe(FALLBACK_COPY);
    expect(arg?.action).toBeUndefined();
  });

  it("falls back gracefully and never throws when reportBug rejects", async () => {
    const api = makeApi(new Error("network down"));
    const notify = vi.fn();

    await expect(
      reportAndNotify({
        error: new Error("boom"),
        context: "ctx.c",
        api,
        notify,
      }),
    ).resolves.toBeUndefined();

    const arg = notify.mock.calls[0]?.[0];
    expect(arg?.message).toBe(FALLBACK_COPY);
    expect(arg?.action).toBeUndefined();
  });

  it("dedupes identical (context,message) errors but still notifies each time", async () => {
    const api = makeApi({
      number: 7,
      url: "https://github.com/acme/repo/issues/7",
      created: true,
    });
    const notify = vi.fn();
    const args = {
      error: new Error("same failure"),
      context: "ctx.d",
      api,
      notify,
    };

    await reportAndNotify(args);
    await reportAndNotify(args);

    expect(api.reportBug).toHaveBeenCalledOnce();
    expect(notify).toHaveBeenCalledTimes(2);
  });

  it("sends a structured payload with message, context, url and user_agent", async () => {
    const api = makeApi({
      number: 1,
      url: "https://github.com/acme/repo/issues/1",
      created: true,
    });
    const notify = vi.fn();

    await reportAndNotify({
      error: new Error("kaboom"),
      context: "ctx.e",
      api,
      notify,
    });

    const payload = api.lastPayload();
    expect(payload?.message).toBe("kaboom");
    expect(payload?.context).toBe("ctx.e");
    expect(typeof payload?.url).toBe("string");
    expect(typeof payload?.user_agent).toBe("string");
  });

  it("does NOT file or notify for expected client errors (4xx)", async () => {
    const api = makeApi({
      number: 9,
      url: "https://github.com/acme/repo/issues/9",
      created: true,
    });
    const notify = vi.fn();

    await reportAndNotify({
      error: new ApiError(409, "Conflict"),
      context: "ctx.4xx",
      api,
      notify,
    });

    expect(api.reportBug).not.toHaveBeenCalled();
    expect(notify).not.toHaveBeenCalled();
  });

  it("does NOT file or notify for a connectivity condition (status 0)", async () => {
    const api = makeApi({
      number: 11,
      url: "https://github.com/acme/repo/issues/11",
      created: true,
    });
    const notify = vi.fn();

    // A dropped/offline connection or timeout (api.ts normalises both to
    // ApiError status 0) is the COMMON case for this persona — surfaced inline
    // by the caller, never filed as a bug nor shown the alarming toast.
    await reportAndNotify({
      error: new ApiError(
        0,
        "You appear to be offline — check your connection.",
      ),
      context: "ctx.offline",
      api,
      notify,
    });

    expect(api.reportBug).not.toHaveBeenCalled();
    expect(notify).not.toHaveBeenCalled();
  });
});

describe("isConnectivityError", () => {
  it("is true for transport/timeout failures (ApiError status 0)", () => {
    expect(isConnectivityError(new ApiError(0, "offline"))).toBe(true);
  });

  it("is false for HTTP responses and generic errors", () => {
    expect(isConnectivityError(new ApiError(500, "Internal"))).toBe(false);
    expect(isConnectivityError(new ApiError(404, "Not Found"))).toBe(false);
    expect(isConnectivityError(new Error("boom"))).toBe(false);
  });
});

describe("isReportableError", () => {
  it("reports transport/runtime errors that carry no HTTP status", () => {
    expect(isReportableError(new Error("network/CORS failure"))).toBe(true);
    expect(isReportableError("boom")).toBe(true);
  });

  it("reports genuine server faults (5xx)", () => {
    expect(isReportableError(new ApiError(500, "Internal"))).toBe(true);
    expect(isReportableError(new ApiError(503, "Unavailable"))).toBe(true);
  });

  it("does NOT report connectivity conditions (status 0: offline/timeout)", () => {
    expect(isReportableError(new ApiError(0, "Network"))).toBe(false);
  });

  it("ignores expected client errors (4xx)", () => {
    expect(isReportableError(new ApiError(401, "Unauthorized"))).toBe(false);
    expect(isReportableError(new ApiError(404, "Not Found"))).toBe(false);
    expect(isReportableError(new ApiError(409, "Conflict"))).toBe(false);
  });
});
