"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type NotificationSeverity = "info" | "success" | "error";

/** Optional call-to-action rendered as a link inside a toast. */
export interface NotificationAction {
  label: string;
  href: string;
}

/** Payload accepted by {@link Notify}. */
export interface NotificationInput {
  severity: NotificationSeverity;
  message: string;
  action?: NotificationAction;
}

/** A queued notification with the id assigned by the provider. */
export interface AppNotification extends NotificationInput {
  id: number;
}

export type Notify = (input: NotificationInput) => void;

interface NotificationContextValue {
  notify: Notify;
}

const NotificationContext = createContext<NotificationContextValue | null>(
  null,
);

const noop: Notify = () => {};

/**
 * Subscribes to the global notifier. Returns a no-op when called outside a
 * {@link NotificationProvider} so isolated component tests can render a tab
 * without wiring up the provider.
 */
export function useNotify(): Notify {
  const ctx = useContext(NotificationContext);
  return ctx?.notify ?? noop;
}

/**
 * App-root provider that owns the notification queue and renders the toast
 * stack. Mount once near the top of the tree; descendants dispatch with
 * {@link useNotify}.
 */
export function NotificationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const notify = useCallback<Notify>((input) => {
    const id = nextId.current++;
    setItems((prev) => [...prev, { ...input, id }]);
  }, []);

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <ToastStack items={items} onDismiss={dismiss} />
    </NotificationContext.Provider>
  );
}

function ToastStack({
  items,
  onDismiss,
}: {
  items: AppNotification[];
  onDismiss: (id: number) => void;
}) {
  if (items.length === 0) return null;
  return (
    <div className="toast-stack">
      {items.map((n) => (
        <div
          key={n.id}
          className={`banner toast ${n.severity}`}
          role={n.severity === "error" ? "alert" : "status"}
        >
          <span className="toast-message">{n.message}</span>
          {n.action && (
            <a
              className="toast-action"
              href={n.action.href}
              target="_blank"
              rel="noreferrer"
            >
              {n.action.label}
            </a>
          )}
          <button
            type="button"
            className="toast-dismiss"
            aria-label="Dismiss notification"
            onClick={() => onDismiss(n.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
