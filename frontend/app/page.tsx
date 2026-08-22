"use client";

import { useEffect, useMemo, useState } from "react";

import { FilterSidebar } from "../components/filters/FilterSidebar";
import { RecommendationCard } from "../components/results/RecommendationCard";
import { ResultsState } from "../components/results/ResultsState";
import { SummaryPanel } from "../components/results/SummaryPanel";
import { Button } from "../components/ui/Button";
import { getCities, getCuisines, getRecommendations } from "../lib/api";
import { BudgetTier, Recommendation, RecommendationResponse } from "../lib/types";

type SortMode = "best" | "rating" | "budget";

interface FilterValues {
  location: string;
  budget: BudgetTier;
  cuisine: string;
  minRating: number;
  additionalPreferences: string[];
  limit: number;
}

const DEFAULT_FILTERS: FilterValues = {
  location: "",
  budget: "medium",
  cuisine: "",
  minRating: 4.0,
  additionalPreferences: ["Unique Concepts", "Quiet Dinner"],
  limit: 5,
};

const BUDGET_WEIGHT: Record<BudgetTier, number> = {
  low: 1,
  medium: 2,
  high: 3,
};

export default function HomePage() {
  const [cities, setCities] = useState<string[]>([]);
  const [cuisines, setCuisines] = useState<string[]>([]);
  const [metaError, setMetaError] = useState<string | null>(null);

  const [filters, setFilters] = useState<FilterValues>(DEFAULT_FILTERS);
  const [sortMode, setSortMode] = useState<SortMode>("best");

  const [response, setResponse] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadMetadata() {
      try {
        setMetaError(null);
        const [cityData, cuisineData] = await Promise.all([getCities(), getCuisines()]);
        if (!active) {
          return;
        }
        setCities(cityData);
        setCuisines(cuisineData);
        setFilters((previous) => ({
          ...previous,
          location: previous.location || cityData[0] || "",
        }));
      } catch (error) {
        if (!active) {
          return;
        }
        setMetaError(error instanceof Error ? error.message : "Failed to load metadata.");
      }
    }

    loadMetadata();

    return () => {
      active = false;
    };
  }, []);

  const sortedRecommendations = useMemo(() => {
    const recommendations = response?.recommendations ?? [];
    const cloned = [...recommendations];

    if (sortMode === "rating") {
      return cloned.sort(
        (a, b) => (b.restaurant.rating ?? -1) - (a.restaurant.rating ?? -1),
      );
    }

    if (sortMode === "budget") {
      return cloned.sort(
        (a, b) => BUDGET_WEIGHT[a.restaurant.budget_tier] - BUDGET_WEIGHT[b.restaurant.budget_tier],
      );
    }

    return cloned.sort((a, b) => a.rank - b.rank);
  }, [response?.recommendations, sortMode]);

  const submitFilters = async () => {
    setLoading(true);
    setRequestError(null);

    try {
      const recommendations = await getRecommendations({
        location: filters.location,
        budget: filters.budget,
        cuisine: filters.cuisine || null,
        min_rating: filters.minRating,
        additional_preferences: filters.additionalPreferences,
        limit: filters.limit,
      });
      setResponse(recommendations);
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Request failed.");
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  const resetFilters = () => {
    setFilters({
      ...DEFAULT_FILTERS,
      location: cities[0] ?? "",
    });
    setResponse(null);
    setRequestError(null);
  };

  const activeCount = sortedRecommendations.length;

  return (
    <>
      <header className="topbar" style={{ padding: "12px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "var(--accent)", fontSize: 30 }}>✕</span>
          <h1 style={{ color: "var(--accent)", fontSize: 29 }}>Zomato AI Recommender</h1>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span
            style={{
              border: "1px solid rgba(43, 49, 64, 0.9)",
              borderRadius: 999,
              padding: "6px 10px",
              background: "rgba(23, 26, 33, 0.8)",
              color: "#d5f5ee",
              fontSize: 12,
            }}
          >
            {metaError ? "API NOT READY" : "API CONNECTED"}
          </span>
        </div>
      </header>

      <div className="app-shell">
        <FilterSidebar
          locations={cities}
          cuisines={cuisines}
          values={filters}
          loading={loading}
          onChange={setFilters}
          onSubmit={submitFilters}
          onReset={resetFilters}
        />

        <main style={{ padding: 20 }}>
          <div style={{ maxWidth: 980, margin: "0 auto", display: "grid", gap: 16 }}>
            <section style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
              <div>
                <h2 style={{ fontSize: 42 }}>AI Curated Selection</h2>
                <p style={{ marginTop: 6, marginBottom: 0, color: "var(--text-secondary)" }}>
                  {activeCount > 0
                    ? `Found ${activeCount} tailored matches in ${filters.location}.`
                    : "Choose preferences to discover your next restaurant."}
                </p>
              </div>

              <div style={{ display: "flex", gap: 8, border: "1px solid var(--border)", borderRadius: 12, padding: 5 }}>
                <Button type="button" onClick={() => setSortMode("best")} className={sortMode === "best" ? "primary" : ""}>
                  Best Match
                </Button>
                <Button type="button" onClick={() => setSortMode("rating")} className={sortMode === "rating" ? "primary" : ""}>
                  Rating
                </Button>
                <Button type="button" onClick={() => setSortMode("budget")} className={sortMode === "budget" ? "primary" : ""}>
                  Budget
                </Button>
              </div>
            </section>

            {metaError ? (
              <section className="panel" style={{ padding: 20 }} role="alert">
                <h3 style={{ color: "var(--danger)", marginBottom: 6 }}>Unable to load metadata</h3>
                <p style={{ marginTop: 0, color: "var(--text-secondary)" }}>{metaError}</p>
                <p style={{ marginBottom: 0, color: "var(--text-secondary)" }}>
                  Ensure FastAPI is running at http://localhost:8000 or set API_BASE_URL / NEXT_PUBLIC_API_BASE_URL.
                </p>
              </section>
            ) : null}

            <SummaryPanel summary={response?.summary ?? null} source={response?.source ?? null} />

            <ResultsState
              loading={loading}
              error={requestError}
              hasResults={sortedRecommendations.length > 0}
              onRetry={submitFilters}
            />

            <div className="results-grid">
              {sortedRecommendations.map((recommendation: Recommendation) => (
                <RecommendationCard recommendation={recommendation} key={recommendation.restaurant.restaurant_id} />
              ))}
            </div>
          </div>
        </main>
      </div>
    </>
  );
}
