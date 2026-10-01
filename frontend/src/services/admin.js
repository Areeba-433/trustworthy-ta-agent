import { apiFetch } from "./api";
export const adminService = {
  getUsers:         (params = {}) => apiFetch(`/admin/users?${new URLSearchParams(params)}`),
  updateUserStatus: (id, is_active) => apiFetch(`/admin/users/${id}/status`, { method: "PATCH", body: { is_active } }),
  promoteToTeacher: (id) => apiFetch(`/admin/users/${id}/role`, { method: "PATCH", body: { role: "TEACHER" } }),
};