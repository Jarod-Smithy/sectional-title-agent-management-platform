/**
 * Shared loading/error presentation for the data-loading tabs.
 *
 * The tabs run an explicit `loading -> (empty | data)` state machine so that on
 * a slow/intermittent connection (this persona's norm) the app shows skeleton
 * placeholders instead of its "Nothing here yet" empty copy before the very
 * first fetch has resolved — empty copy before a resolved fetch looks broken.
 */

/** A shimmering placeholder line; widths vary so rows feel organic. */
function SkeletonLine({ width }: { width: string }) {
  return <div className="skeleton-line" style={{ width }} aria-hidden="true" />;
}

/** Placeholder `.list-row`s shown while a list is loading for the first time. */
export function SkeletonList({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton" role="status" aria-label="Loading…">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="list-row">
          <SkeletonLine width="60%" />
          <SkeletonLine width="35%" />
        </div>
      ))}
    </div>
  );
}

/** Placeholder `.card`s for the board columns while tasks are loading. */
export function SkeletonCards({ cards = 2 }: { cards?: number }) {
  return (
    <div className="skeleton" role="status" aria-label="Loading…">
      {Array.from({ length: cards }, (_, i) => (
        <div key={i} className="card">
          <SkeletonLine width="80%" />
          <SkeletonLine width="50%" />
        </div>
      ))}
    </div>
  );
}

/**
 * An inline error with a "Try again" button so a transient failure (offline,
 * timeout, server hiccup) is recoverable in place — previously the only way to
 * re-fetch was to switch tabs.
 */
export function RetryableError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="banner error retryable" role="alert">
      <span>{message}</span>
      <button className="btn ghost" type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}
