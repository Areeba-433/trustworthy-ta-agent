const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const authService = {
    login: async (data) => {
        const res = await fetch(`${BASE}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(data),
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
    register: async (data) => {
        const res = await fetch(`${BASE}/api/v1/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(data),
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
    verifyEmail: async (token) => {
        const res = await fetch(`${BASE}/api/v1/auth/verify-email?token=${token}`, {
            credentials: "include",
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
    forgotPassword: async (email) => {
        const res = await fetch(`${BASE}/api/v1/auth/forgot-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ email }),
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
    resetPassword: async (data) => {
        const res = await fetch(`${BASE}/api/v1/auth/reset-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(data),
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
    logout: async () => {
        await fetch(`${BASE}/api/v1/auth/logout`, {
            method: "POST",
            credentials: "include",
        });
    },
    getMe: async () => {
        const res = await fetch(`${BASE}/api/v1/auth/me`, {
            credentials: "include",
        });
        if (!res.ok) throw new Error("Unauthorized");
        return res.json();
    },
};