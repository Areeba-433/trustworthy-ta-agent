import { useState } from "react";
import { adminApi } from "../../services/api/adminApi";

export default function UserStatusToggle({ user, onUpdated }) {
    const [loading, setLoading] = useState(false);

    const handleToggle = async () => {
        setLoading(true);
        try {
            const res = await adminApi.updateUserStatus(user.id, !user.is_active);
            onUpdated(res.data.user);
        } catch (err) {
            alert(err?.detail?.error?.message || "Failed to update user status.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <button
            onClick={handleToggle}
            disabled={loading}
            className={
                user.is_active
                    ? "px-3 py-1 text-xs font-medium rounded bg-red-50 text-red-600 hover:bg-red-100 disabled:opacity-50"
                    : "px-3 py-1 text-xs font-medium rounded bg-green-50 text-green-600 hover:bg-green-100 disabled:opacity-50"
            }
        >
            {loading ? "..." : user.is_active ? "Deactivate" : "Activate"}
        </button>
    );
}