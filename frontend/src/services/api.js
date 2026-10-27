/** Small fetch wrapper for the SmartChunk FastAPI backend. */

export function resolveApiBase() {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");

  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    // GitHub Codespaces forwarded URLs typically look like <name>-5173.app.github.dev.
    if (hostname.endsWith(".app.github.dev") && /-5173\.app\.github\.dev$/.test(hostname)) {
      return `${protocol}//${hostname.replace(/-5173\.app\.github\.dev$/, "-8000.app.github.dev")}`;
    }
  }
  return "http://127.0.0.1:8000";
}

export const API_BASE = resolveApiBase();

async function readResponse(response) {
  if (response.status === 204) return {};
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    let detail = payload?.detail;
    if (Array.isArray(detail)) {
      detail = detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
    throw new Error(typeof detail === "string" ? detail : `Request failed with HTTP ${response.status}.`);
  }
  return payload;
}

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  return readResponse(response);
}

export function apiGet(path) {
  return apiRequest(path, { method: "GET" });
}

export function apiPostJson(path, value) {
  return apiRequest(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value),
  });
}

export function apiPost(path) {
  return apiRequest(path, { method: "POST" });
}

export function apiPostFile(path, file, fields = {}) {
  if (!file) return Promise.reject(new Error("Choose a document first."));
  const body = new FormData();
  body.append("file", file);
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null && value !== "") body.append(key, String(value));
  }
  return apiRequest(path, { method: "POST", body });
}
