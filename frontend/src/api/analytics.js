import { api } from "./client";

export const analyticsApi = {
  runAnalysis: (locationId) => api.post("/api/analysis/run", { location_id: locationId }),

  listAnomalies: ({ resourceId, locationId, resourceType, severity, status, classification } = {}) => {
    const params = new URLSearchParams();
    if (resourceId) params.set("resource_id", resourceId);
    if (locationId) params.set("location_id", locationId);
    if (resourceType) params.set("resource_type", resourceType);
    if (severity) params.set("severity", severity);
    if (status) params.set("status", status);
    if (classification) params.set("classification", classification);
    const qs = params.toString();
    return api.get(`/api/anomalies${qs ? `?${qs}` : ""}`);
  },

  getAnomaly: (anomalyId) => api.get(`/api/anomalies/${anomalyId}`),

  getResourceBaselines: (resourceId) => api.get(`/api/resources/${resourceId}/baselines`),

  getFactors: () => api.get("/api/config/factors"),
};
