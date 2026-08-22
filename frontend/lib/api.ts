import {
  CitiesResponse,
  CuisinesResponse,
  LocationsResponse,
  RecommendationRequest,
  RecommendationResponse,
} from "./types";

const API_BASE_URL = "/backend";

async function parseJsonOrThrow<T>(response: Response): Promise<T> {
  const payload = await response.json();
  if (!response.ok) {
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : JSON.stringify(payload?.detail ?? payload);
    throw new Error(detail || "Request failed");
  }
  return payload as T;
}

export async function getCities(): Promise<string[]> {
  const citiesResp = await fetch(`${API_BASE_URL}/api/v1/meta/cities`);
  if (citiesResp.ok) {
    const data = await parseJsonOrThrow<CitiesResponse>(citiesResp);
    return data.cities;
  }

  const locationsResp = await fetch(`${API_BASE_URL}/api/v1/meta/locations`);
  const fallback = await parseJsonOrThrow<LocationsResponse>(locationsResp);
  return fallback.locations;
}

export async function getCuisines(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/meta/cuisines`);
  const data = await parseJsonOrThrow<CuisinesResponse>(response);
  return data.cuisines;
}

export async function getRecommendations(
  body: RecommendationRequest,
): Promise<RecommendationResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/recommendations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  return parseJsonOrThrow<RecommendationResponse>(response);
}
