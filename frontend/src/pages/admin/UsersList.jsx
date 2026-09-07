import { useState, useEffect } from "react";
import { adminApi } from "../../services/api/adminApi";
import UserStatusToggle from "../../components/admin/UserStatusToggle";

export default function UsersList() {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [search, setSearch] = useState("");
    const [page, setPage] = useState(1);
    const [pagination, setPagination] = useState({ total: 0, limit: 20 });

    const loadUsers = async () => {
        setLoading(true);
        setError("");
        try {
            const res = await adminApi.getUsers({ page, limit: 20, search });
            setUsers(res.data.users);
            setPagination(res.data.pagination);
        } catch (err) {
            setError(err?.detail?.error?.message || "Failed to load users.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadUsers();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page]);

    const handleStatusUpdated = (updatedUser) => {
        setUsers((prev) =>
            prev.map((u) => (u.id === updatedUser.id ? { ...u, is_active: updatedUser.is_active } : u))
        );
    };

    const handleSearchSubmit = (e) => {
        e.preventDefault();
        setPage(1);
        loadUsers();
    };

    return (
        <div className="p-6 max-w-6xl mx-auto">
            <h1 className="text-2xl font-semibold text-gray-800 mb-4">User Management</h1>

            <form onSubmit={handleSearchSubmit} className="mb-4 flex gap-2">
                <input
                    type="text"
                    placeholder="Search by email..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1 max-w-sm"
                />
                <button
                    type="submit"
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
                >
                    Search
                </button>
            </form>

            {error && (
                <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3 mb-4">
                    {error}
                </div>
            )}

            {loading ? (
                <p className="text-gray-500 text-sm">Loading users...</p>
            ) : users.length === 0 ? (
                <p className="text-gray-500 text-sm">No users found.</p>
            ) : (
                <div className="overflow-x-auto border border-gray-200 rounded-lg">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-gray-50 text-gray-600">
                            <tr>
                                <th className="px-4 py-3">Username</th>
                                <th className="px-4 py-3">Email</th>
                                <th className="px-4 py-3">Role</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map((u) => (
                                <tr key={u.id} className="border-t border-gray-100">
                                    <td className="px-4 py-3">{u.username}</td>
                                    <td className="px-4 py-3">{u.email}</td>
                                    <td className="px-4 py-3">{u.role}</td>
                                    <td className="px-4 py-3">
                                        <span
                                            className={
                                                u.is_active
                                                    ? "text-green-600 font-medium"
                                                    : "text-red-500 font-medium"
                                            }
                                        >
                                            {u.is_active ? "Active" : "Deactivated"}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3">
                                        <UserStatusToggle user={u} onUpdated={handleStatusUpdated} />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <div className="flex justify-between items-center mt-4 text-sm text-gray-500">
                <span>
                    Page {page} of {Math.max(1, Math.ceil(pagination.total / pagination.limit))}
                </span>
                <div className="flex gap-2">
                    <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40"
                    >
                        Previous
                    </button>
                    <button
                        onClick={() => setPage((p) => p + 1)}
                        disabled={page * pagination.limit >= pagination.total}
                        className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40"
                    >
                        Next
                    </button>
                </div>
            </div>
        </div>
    );
}