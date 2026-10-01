import { apiFetch } from "./api";
export const authService = {
  login:          (data)  => apiFetch("/auth/login", { method: "POST", body: data }),
  register:       (data)  => apiFetch("/auth/register", { method: "POST", body: data }),
  verifyEmail:    (token) => apiFetch(`/auth/verify-email?token=${encodeURIComponent(token)}`),
  forgotPassword: (email) => apiFetch("/auth/forgot-password", { method: "POST", body: { email } }),
  resetPassword:  (data)  => apiFetch("/auth/reset-password", { method: "POST", body: data }),
  logout:         ()      => apiFetch("/auth/logout", { method: "POST" }).catch(() => {}),
  getMe:          ()      => apiFetch("/auth/me"),
};