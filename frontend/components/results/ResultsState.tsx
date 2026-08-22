import { Skeleton } from "../ui/Skeleton";

interface ResultsStateProps {
  loading: boolean;
  error: string | null;
  hasResults: boolean;
  onRetry: () => void;
}

export function ResultsState({
  loading,
  error,
  hasResults,
  onRetry,
}: ResultsStateProps) {
  if (loading) {
    return (
      <div className="results-grid" aria-live="polite">
        <Skeleton height={160} />
        <Skeleton height={210} />
        <Skeleton height={210} />
      </div>
    );
  }

  if (error) {
    return (
      <section className="panel" style={{ padding: 20 }} role="alert">
        <h3 style={{ marginBottom: 6, color: "var(--danger)" }}>Could not fetch recommendations</h3>
        <p style={{ marginTop: 0, color: "var(--text-secondary)" }}>{error}</p>
        <button type="button" className="button" onClick={onRetry}>
          Retry
        </button>
      </section>
    );
  }

  if (!hasResults) {
    return (
      <section className="panel" style={{ padding: 20 }}>
        <h3 style={{ marginBottom: 6 }}>No recommendations yet</h3>
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>
          Set your filters and request recommendations to see curated matches.
        </p>
      </section>
    );
  }

  return null;
}
