import { api } from "./client";

export const telemetryApi = {
  listLocations: () => api.get("/api/locations"),

  listResources: ({ locationId, resourceType } = {}) => {
    const params = new URLSearchParams();
    if (locationId) params.set("location_id", locationId);
    if (resourceType) params.set("resource_type", resourceType);
    const qs = params.toString();
    return api.get(`/api/resources${qs ? `?${qs}` : ""}`);
  },

  getMeasurements: ({ resourceId, locationId, resourceType, start, end, limit = 500, offset = 0 } = {}) => {
    const params = new URLSearchParams();
    if (resourceId) params.set("resource_id", resourceId);
    if (locationId) params.set("location_id", locationId);
    if (resourceType) params.set("resource_type", resourceType);
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    params.set("limit", limit);
    params.set("offset", offset);
    return api.get(`/api/measurements?${params.toString()}`);
  },

  /** Fetches the most recent measurements for a resource without requiring
   * the backend to support a "latest first" sort — two lightweight calls
   * (first to learn the total count, then to fetch the tail) rather than
   * pulling the whole history to sort client-side. */
  getRecentMeasurements: async ({ resourceId, count = 48 }) => {
    const first = await telemetryApi.getMeasurements({ resourceId, limit: 1, offset: 0 });
    const total = first.total;
    if (total === 0) return [];
    const offset = Math.max(0, total - count);
    const page = await telemetryApi.getMeasurements({ resourceId, limit: count, offset });
    return page.items;
  },

  uploadCsv: (file) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.postForm("/api/data/upload", formData);
  },

  simulate: ({ scenario, locationName, seed, weeks }) =>
    api.post("/api/data/simulate", { scenario, location_name: locationName, seed, weeks }),

  liveTick: ({ locationId, hours = 1, seed = 42 }) =>
    api.post("/api/data/live/tick", { location_id: locationId, hours, seed }),
};
