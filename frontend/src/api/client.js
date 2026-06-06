import axios from "axios";

const BASE_URL = "http://127.0.0.1:8000";

export function getApiKey() {
  return localStorage.getItem("chronolens_api_key") || "";
}

export function setApiKey(key) {
  localStorage.setItem("chronolens_api_key", key);
}

const client = axios.create({ baseURL: BASE_URL });

client.interceptors.request.use((config) => {
  const key = getApiKey();
  if (key) config.headers["X-API-Key"] = key;
  return config;
});

function errMsg(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "object" && detail !== null) {
    return detail.reason || detail.error || "Security scan blocked this request";
  }
  return detail || error?.message || "Request failed";
}

export async function uploadDocument(formData) {
  try {
    const res = await client.post("/api/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  } catch (e) { throw new Error(errMsg(e), { cause: e }); }
}

export async function getVersions(documentId) {
  try {
    const res = await client.get(`/api/documents/${documentId}/versions`);
    return res.data;
  } catch (e) { throw new Error(errMsg(e), { cause: e }); }
}

export async function getStats() {
  try {
    const res = await client.get("/api/documents/stats");
    return res.data;
  } catch (e) { throw new Error(errMsg(e), { cause: e }); }
}

export async function askQuestion(documentId, question) {
  try {
    const res = await client.post("/api/query/ask", {
      document_id: documentId,
      question,
    });
    return res.data;
  } catch (e) { throw new Error(errMsg(e), { cause: e }); }
}

export async function compareVersions(documentId, versionA, versionB, aspect) {
  try {
    const res = await client.post("/api/query/compare", {
      document_id: documentId,
      version_a: versionA,
      version_b: versionB,
      aspect: aspect || null,
    });
    return res.data;
  } catch (e) { throw new Error(errMsg(e), { cause: e }); }
}

export async function getTimeline(documentId) {
  try {
    const res = await client.get(`/api/query/timeline/${documentId}`);
    return res.data;
  } catch (e) { throw new Error(errMsg(e), { cause: e }); }
}
export async function semanticDiff(documentId, versionA, versionB) {
  try {
    const res = await client.post("/api/query/semantic-diff", {
      document_id: documentId,
      version_a: versionA,
      version_b: versionB,
    });
    return res.data;
  } catch (e) { throw new Error(errMsg(e), { cause: e }); }
}
export async function causalGraph(documentId) {
  try {
    const res = await client.get(`/api/query/causal-graph/${documentId}`);
    return res.data;
  } catch (e) { throw new Error(errMsg(e), { cause: e }); }
}