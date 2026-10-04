import { apiFetch } from "./api";

export const taService = {
  list:   ()         => apiFetch("/teaching-assistants"),
  create: (data)     => apiFetch("/teaching-assistants", { method: "POST", body: data }),
  update: (id, data) => apiFetch(`/teaching-assistants/${id}`, { method: "PUT", body: data }),
  remove: (id)       => apiFetch(`/teaching-assistants/${id}`, { method: "DELETE" }),
};