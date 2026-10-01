const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "") + "/api/v1";
const NO_REFRESH = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/forgot-password", "/auth/reset-password", "/auth/verify-email"];

let refreshing = null;
const tryRefresh = () => (refreshing ??= fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include" })
  .then(r => r.ok).catch(() => false).finally(() => { refreshing = null; }));

export async function apiFetch(path, { body, headers, _retried, ...options } = {}) {
  const isForm = body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: { ...(body && !isForm ? { "Content-Type": "application/json" } : {}), ...headers },
    body: body && !isForm ? JSON.stringify(body) : body,
  });

  if (res.status === 401 && !_retried && !NO_REFRESH.some(p => path.startsWith(p)) && await tryRefresh()) {
    return apiFetch(path, { body, headers, ...options, _retried: true });
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    let err;
    if (Array.isArray(d)) err = { error: { code: "VALIDATION_ERROR", message: d[0]?.msg?.replace(/^Value error, /, "") ?? "Invalid input" } };
    else if (d && typeof d === "object") err = d;
    else err = { error: { code: `HTTP_${res.status}`, message: typeof d === "string" ? d : "Request failed" } };
    throw { ...err, status: res.status };
  }
  return data;
}