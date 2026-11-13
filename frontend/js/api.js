// Central fetch wrapper — every backend call goes through here.
// The API host follows whatever host the page itself was opened from.
// This matters: the login session lives in a cookie, and browsers treat
// "localhost" and "127.0.0.1" as different sites, so a page opened from
// http://127.0.0.1:5500 that calls http://localhost:5000 will silently lose
// its session cookie (login "succeeds" but you get bounced back to auth.html).
// To point at a deployed backend, set window.SHELFWISE_API_BASE before this
// script loads, e.g. <script>window.SHELFWISE_API_BASE = "https://api.example.com/api"</script>
const API_BASE = "/api";

async function apiRequest(method, path, body) {
  const opts = {
    method,
    credentials: "include", // send the Flask session cookie
    headers: {},
  };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, opts);
  } catch (err) {
    throw new Error("Can't reach the ShelfWise server. Is the Flask backend running on port 5000?");
  }
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : null;
  if (!res.ok) {
    throw new Error((data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

const api = {
  get: (path) => apiRequest("GET", path),
  post: (path, body) => apiRequest("POST", path, body ?? {}),
  put: (path, body) => apiRequest("PUT", path, body ?? {}),
  del: (path) => apiRequest("DELETE", path),
};
