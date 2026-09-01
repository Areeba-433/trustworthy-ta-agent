const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const authService = {
    login: async (data) => {
        const res = await fetch(`${BASE}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },

    logout: async (token) => {
        await fetch(`${BASE}/api/auth/logout`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
        });
    },

    getMe: async (token) => {
        const res = await fetch(`${BASE}/api/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Unauthorized");
        return res.json();
    },

    refresh: async (refreshToken) => {
        const res = await fetch(`${BASE}/api/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) throw new Error("Refresh failed");
        return res.json();
    },
};