const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const userService = {
    getProfile: async () => {
        const res = await fetch(`${BASE}/api/v1/users/me`, {
            credentials: "include",
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
    updateProfile: async (data) => {
        const res = await fetch(`${BASE}/api/v1/users/me`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(data),
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
    uploadAvatar: async (file) => {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch(`${BASE}/api/v1/users/me/avatar`, {
            method: "POST",
            credentials: "include",
            body: formData,
        });
        if (!res.ok) throw await res.json();
        return res.json();
    },
};