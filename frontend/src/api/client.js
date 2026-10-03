/**
 * Base API client (docs Milestone 6, requirement #30).
 *
 * Every backend request goes through here rather than scattering fetch()
 * calls through components. Reads the backend base URL from an environment
 * variable — never hardcoded — and normalizes error handling so callers
 * always get either parsed JSON or a thrown ApiError with a readable
 * message (matching the backend's {error: {code, message, details}}
 * convention documented in API.md).
 */

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, { status, code, details } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request(path, { method = "GET", body, isFormData = false } = {}) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: isFormData ? undefined : { "Content-Type": "application/json" },
      body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
    });
  } catch (networkError) {
    throw new ApiError("Could not reach the EcoTwin backend. Is it running?", {
      status: 0,
      code: "network_error",
    });
  }

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const errorBody = payload?.error;
    throw new ApiError(errorBody?.message || `Request failed (${response.status})`, {
      status: response.status,
      code: errorBody?.code,
      details: errorBody?.details,
    });
  }

  return payload;
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body: body ?? {} }),
  put: (path, body) => request(path, { method: "PUT", body: body ?? {} }),
  postForm: (path, formData) => request(path, { method: "POST", body: formData, isFormData: true }),
};

export { BASE_URL };
