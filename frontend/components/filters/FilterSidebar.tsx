import { BudgetTier } from "../../lib/types";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";

const PREFERENCE_OPTIONS = [
  "Unique Concepts",
  "Outdoor seating",
  "Vegan-friendly",
  "Quiet Dinner",
  "Family-friendly",
  "Quick service",
];

interface FilterValues {
  location: string;
  budget: BudgetTier;
  cuisine: string;
  minRating: number;
  additionalPreferences: string[];
  limit: number;
}

interface FilterSidebarProps {
  locations: string[];
  cuisines: string[];
  values: FilterValues;
  loading: boolean;
  onChange: (next: FilterValues) => void;
  onSubmit: () => void;
  onReset: () => void;
}

export function FilterSidebar({
  locations,
  cuisines,
  values,
  loading,
  onChange,
  onSubmit,
  onReset,
}: FilterSidebarProps) {
  const togglePreference = (value: string) => {
    const exists = values.additionalPreferences.includes(value);
    const next = exists
      ? values.additionalPreferences.filter((item) => item !== value)
      : [...values.additionalPreferences, value];

    onChange({ ...values, additionalPreferences: next });
  };

  return (
    <aside
      style={{
        padding: 20,
        borderRight: "1px solid rgba(43, 49, 64, 0.85)",
        background: "rgba(23, 26, 33, 0.78)",
      }}
    >
      <h2 style={{ fontSize: 28, marginBottom: 4 }}>Filters</h2>
      <p style={{ color: "var(--text-secondary)", marginTop: 0, marginBottom: 18 }}>
        Refine your AI taste
      </p>

      <label htmlFor="city" style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>
        CITY
      </label>
      <select
        id="city"
        className="control"
        value={values.location}
        onChange={(event) => onChange({ ...values, location: event.target.value })}
        style={{ marginTop: 8, marginBottom: 14 }}
      >
        {locations.length === 0 ? (
          <option value="">Loading cities...</option>
        ) : null}
        {locations.map((location) => (
          <option key={location} value={location}>
            {location}
          </option>
        ))}
      </select>

      <label htmlFor="cuisine" style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>
        CUISINE TYPE
      </label>
      <select
        id="cuisine"
        className="control"
        value={values.cuisine}
        onChange={(event) => onChange({ ...values, cuisine: event.target.value })}
        style={{ marginTop: 8, marginBottom: 14 }}
      >
        <option value="">Any cuisine</option>
        {cuisines.map((cuisine) => (
          <option key={cuisine} value={cuisine}>
            {cuisine}
          </option>
        ))}
      </select>

      <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 8 }}>
        BUDGET
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6, marginBottom: 14 }}>
        {(["low", "medium", "high"] as BudgetTier[]).map((budget) => {
          const active = budget === values.budget;
          return (
            <button
              key={budget}
              className="button"
              onClick={() => onChange({ ...values, budget })}
              style={{
                textTransform: "capitalize",
                background: active ? "var(--surface-3)" : "rgba(23, 26, 33, 0.9)",
                borderColor: active ? "rgba(255, 107, 53, 0.55)" : "var(--border)",
                color: active ? "var(--accent)" : "var(--text-secondary)",
              }}
              type="button"
            >
              {budget}
            </button>
          );
        })}
      </div>

      <label htmlFor="rating" style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>
        <span>MIN RATING</span>
        <span className="metric">{values.minRating.toFixed(1)}</span>
      </label>
      <input
        id="rating"
        type="range"
        min={0}
        max={5}
        step={0.1}
        value={values.minRating}
        onChange={(event) => onChange({ ...values, minRating: Number(event.target.value) })}
        style={{ width: "100%", accentColor: "#ff6b35", marginBottom: 16 }}
      />

      <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 8 }}>
        ADDITIONAL PREFERENCES
      </p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {PREFERENCE_OPTIONS.map((option) => (
          <Chip
            key={option}
            active={values.additionalPreferences.includes(option)}
            onClick={() => togglePreference(option)}
            type="button"
          >
            {option}
          </Chip>
        ))}
      </div>

      <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 8 }}>
        RESULT LIMIT
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "42px 1fr 42px", gap: 8, marginBottom: 18 }}>
        <Button
          type="button"
          onClick={() => onChange({ ...values, limit: Math.max(1, values.limit - 1) })}
        >
          -
        </Button>
        <div
          style={{
            display: "grid",
            placeItems: "center",
            borderRadius: 12,
            border: "1px solid var(--border)",
            background: "rgba(15, 17, 21, 0.92)",
          }}
        >
          {values.limit}
        </div>
        <Button
          type="button"
          onClick={() => onChange({ ...values, limit: Math.min(20, values.limit + 1) })}
        >
          +
        </Button>
      </div>

      <div style={{ display: "grid", gap: 10 }}>
        <Button type="button" variant="primary" disabled={loading || !values.location} onClick={onSubmit}>
          {loading ? "Getting Recommendations..." : "Get Recommendations"}
        </Button>
        <Button type="button" onClick={onReset}>
          Reset filters
        </Button>
      </div>
    </aside>
  );
}
