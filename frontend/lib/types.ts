export type BudgetTier = "low" | "medium" | "high";

export interface Restaurant {
  restaurant_id: string;
  name: string;
  location: string;
  city: string;
  address: string;
  cuisines: string[];
  cost_for_two: number | null;
  budget_tier: BudgetTier;
  rating: number | null;
  votes: number;
}

export interface Recommendation {
  restaurant: Restaurant;
  rank: number;
  explanation: string;
}

export interface RecommendationResponse {
  summary: string | null;
  recommendations: Recommendation[];
  source: "llm" | "fallback" | string;
}

export interface RecommendationRequest {
  location: string;
  budget: BudgetTier;
  cuisine: string | null;
  min_rating: number | null;
  additional_preferences: string[];
  limit: number;
}

interface CountResponse {
  count: number;
}

export interface CitiesResponse extends CountResponse {
  cities: string[];
}

export interface LocationsResponse extends CountResponse {
  locations: string[];
}

export interface CuisinesResponse extends CountResponse {
  cuisines: string[];
}
