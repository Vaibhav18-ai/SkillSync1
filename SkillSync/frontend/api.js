const API = "http://127.0.0.1:8000/api";

async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("token");
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) { localStorage.clear(); location.href = "login.html"; }
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Please check the details and try again.");
  return data;
}

function requireRole(role) {
  const user = JSON.parse(localStorage.getItem("user") || "null");
  if (!user || user.role !== role) location.href = "login.html";
  return user;
}

function logout() { localStorage.clear(); location.href = "login.html"; }