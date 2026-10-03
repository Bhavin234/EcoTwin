import { api } from "./client";

export const investigationApi = {
  investigate: (anomalyId, { force = false } = {}) => api.post(`/api/anomalies/${anomalyId}/investigate`, { force }),
};

export const interventionApi = {
  create: (investigationId) => api.post(`/api/investigations/${investigationId}/interventions`, {}),
  get: (interventionId) => api.get(`/api/interventions/${interventionId}`),
  complete: (interventionId, completedAt) => api.post(`/api/interventions/${interventionId}/complete`, { completed_at: completedAt }),
  verify: (interventionId) => api.post(`/api/interventions/${interventionId}/verify`, {}),
};

export const impactApi = {
  getImpact: ({ locationId, resourceType } = {}) => {
    const params = new URLSearchParams();
    if (locationId) params.set("location_id", locationId);
    if (resourceType) params.set("resource_type", resourceType);
    const qs = params.toString();
    return api.get(`/api/impact${qs ? `?${qs}` : ""}`);
  },
};

export const demoApi = {
  run: ({ scenario, locationName } = {}) => api.post("/api/demo/run", { scenario, location_name: locationName }),
  reset: ({ locationName } = {}) => api.post("/api/demo/reset", { location_name: locationName }),
};

export const healthApi = {
  check: () => api.get("/api/health"),
};
