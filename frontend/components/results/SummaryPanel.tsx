import { Panel } from "../ui/Panel";

interface SummaryPanelProps {
  summary: string | null;
  source: string | null;
}

export function SummaryPanel({ summary, source }: SummaryPanelProps) {
  if (!summary) {
    return null;
  }

  return (
    <Panel className="summary" >
      <div style={{ padding: 18 }}>
        <h3 style={{ marginBottom: 8, color: "#ffd7c9" }}>Concierge Summary</h3>
        <p style={{ color: "#ead6cd", margin: 0, lineHeight: 1.5 }}>{summary}</p>
        {source ? (
          <p style={{ marginTop: 10, marginBottom: 0, fontSize: 12, color: "var(--text-secondary)" }}>
            Source: {source.toUpperCase()}
          </p>
        ) : null}
      </div>
    </Panel>
  );
}
