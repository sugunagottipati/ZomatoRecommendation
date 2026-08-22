import { describe, expect, it, vi } from "vitest";

import { getCities } from "../lib/api";

describe("getCities", () => {
  it("uses /meta/cities when available", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ cities: ["Koramangala"], count: 1 }), { status: 200 }),
    );

    const cities = await getCities();
    expect(cities).toEqual(["Koramangala"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fetchMock.mockRestore();
  });

  it("falls back to /meta/locations when /meta/cities fails", async () => {
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "missing" }), { status: 404 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ locations: ["Indiranagar"], count: 1 }), { status: 200 }),
      );

    const cities = await getCities();
    expect(cities).toEqual(["Indiranagar"]);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    fetchMock.mockRestore();
  });
});
