import { Recommendation } from "../../lib/types";
import { Button } from "../ui/Button";

interface RecommendationCardProps {
  recommendation: Recommendation;
}

function formatCost(costForTwo: number | null): string {
  if (costForTwo === null) {
    return "Cost unavailable";
  }
  return `INR ${Math.round(costForTwo)} for two`;
}

export function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const { rank, explanation, restaurant } = recommendation;

  return (
    <article className="rec-card" role="article" aria-label={`Recommendation #${rank}`}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 14, marginBottom: 10 }}>
        <div>
          <p style={{ margin: 0, fontSize: 12, color: "var(--accent-strong)", fontWeight: 700 }}>
            #{rank} BEST MATCH
          </p>
          <h3 style={{ fontSize: 30, marginTop: 2 }}>{restaurant.name}</h3>
          <p style={{ marginTop: 6, marginBottom: 0, color: "var(--text-secondary)" }}>
            {restaurant.cuisines.join(", ")} · {restaurant.location}
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <p style={{ margin: 0, fontWeight: 700 }}>{restaurant.rating ?? "N/A"}★</p>
          <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: 12 }}>
            {restaurant.votes} votes
          </p>
        </div>
      </div>

      <div
        style={{
          border: "1px solid rgba(255, 107, 53, 0.3)",
          borderRadius: 12,
          background: "rgba(255, 107, 53, 0.08)",
          padding: 12,
          color: "#f8ddd4",
          marginBottom: 12,
        }}
      >
        <p style={{ margin: 0, fontSize: 12, letterSpacing: "0.05em", color: "#ffc9b5", fontWeight: 700 }}>
          AI REASONING
        </p>
        <p style={{ marginBottom: 0, marginTop: 6, lineHeight: 1.45 }}>{explanation}</p>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>{formatCost(restaurant.cost_for_two)}</p>
        <div style={{ display: "flex", gap: 8 }}>
          <Button type="button">View Details</Button>
          <Button type="button" variant="primary">Book Table</Button>
        </div>
      </div>
    </article>
  );
}
