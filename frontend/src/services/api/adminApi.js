const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const adminApi = {
    getUsers: async (params = {}) => {
        const query = new URLSearchParams(params).toString();
        const res = await fetch(`${BASE}/api/v1/admin/users?${query}`, {
            credentials: "include",
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
    updateUserStatus: async (userId, isActive) => {
        const res = await fetch(`${BASE}/api/v1/admin/users/${userId}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ is_active: isActive }),
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
};