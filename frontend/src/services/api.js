const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";

export async function apiFetch(path, options = {}) {
    const res = await fetch(`${BASE}${path}`, {
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
        ...options,
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
        throw data.detail ?? data;
    }

    return data;
}
