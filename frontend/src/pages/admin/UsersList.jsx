import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Filter, Shield, LogOut, CheckCircle2, XCircle, ChevronLeft, ChevronRight } from "lucide-react";
import toast from "react-hot-toast";
import { adminService } from "../../services/admin";
import { useAuth } from "../../context/AuthContext";
import Background from "../../components/common/Background";

export default function UsersList() {
    const { logout } = useAuth();
    const [users, setUsers]   = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [role, setRole]     = useState("");
    const [page, setPage]     = useState(1);
    const [total, setTotal]   = useState(0);

    const fetchUsers = async () => {
        setLoading(true);
        try {
            const params = { page, limit: 10 };
            if (search) params.search = search;
            if (role)   params.role   = role;
            const res = await adminService.getUsers(params);
            setUsers(res.data?.users || []);
            setTotal(res.data?.pagination?.total || res.data?.total || 0);
        } catch {
            toast.error("Failed to load users");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchUsers(); }, [page, role]);

    const toggleStatus = async (userId, currentStatus) => {
        try {
            await adminService.updateUserStatus(userId, !currentStatus);
            toast.success(currentStatus ? "User deactivated" : "User activated");
            fetchUsers();
        } catch {
            toast.error("Action failed");
        }
    };

    const roleBadge  = {
        ADMIN:   "bg-rose-50 text-rose-600 border-rose-200",
        TEACHER: "bg-purple-50 text-purple-600 border-purple-200",
        STUDENT: "bg-blue-50 text-blue-600 border-blue-200",
    };
    const roleAvatar = {
        ADMIN:   "from-rose-500 to-pink-500",
        TEACHER: "from-purple-500 to-indigo-500",
        STUDENT: "from-blue-500 to-indigo-500",
    };

    return (
        <div className="min-h-screen px-4 py-12 relative">
            <Background />
            <div className="max-w-6xl mx-auto">
                <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between mb-8">
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-600 to-blue-600 flex items-center justify-center">
                                <Shield className="w-4 h-4 text-white" />
                            </div>
                            <span className="font-heading font-semibold text-slate-800">Admin Panel</span>
                        </div>
                        <h1 className="font-heading text-2xl font-bold text-slate-800">User Management</h1>
                    </div>
                    <button onClick={logout}
                        className="flex items-center gap-2 text-sm text-slate-500 hover:text-red-500 transition-colors bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-sm">
                        <LogOut className="w-4 h-4" /> Logout
                    </button>
                </motion.div>

                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="grid grid-cols-3 gap-4 mb-6">
                    {[
                        { label: "Total Users", value: total, color: "text-indigo-600" },
                        { label: "Active",      value: users.filter(u => u.is_active).length, color: "text-emerald-600" },
                        { label: "Inactive",    value: users.filter(u => !u.is_active).length, color: "text-red-500" },
                    ].map(stat => (
                        <div key={stat.label} className="edu-card rounded-2xl p-5">
                            <p className={`font-heading text-3xl font-bold ${stat.color}`}>{stat.value}</p>
                            <p className="text-xs text-slate-400 mt-1">{stat.label}</p>
                        </div>
                    ))}
                </motion.div>

                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="edu-card rounded-2xl p-4 mb-6 flex gap-3">
                    <div className="relative flex-1">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input type="text" placeholder="Search by name or email..."
                            className="edu-input w-full pl-11 pr-4 py-2.5 rounded-xl text-slate-800 placeholder:text-slate-400 text-sm focus:outline-none"
                            value={search} onChange={e => setSearch(e.target.value)}
                            onKeyDown={e => e.key === "Enter" && fetchUsers()} />
                    </div>
                    <div className="relative">
                        <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                        <select
                            className="edu-input pl-11 pr-8 py-2.5 rounded-xl text-slate-800 text-sm focus:outline-none appearance-none cursor-pointer"
                            value={role} onChange={e => { setRole(e.target.value); setPage(1); }}>
                            <option value="">All Roles</option>
                            <option value="STUDENT">Student</option>
                            <option value="TEACHER">Teacher</option>
                            <option value="ADMIN">Admin</option>
                        </select>
                    </div>
                </motion.div>

                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="edu-card rounded-2xl overflow-hidden">
                    {loading ? (
                        <div className="flex items-center justify-center py-20">
                            <motion.div
                                animate={{ rotate: 360 }}
                                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                                className="w-8 h-8 border-4 border-indigo-100 border-t-indigo-600 rounded-full"
                            />
                        </div>
                    ) : (
                        <>
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-slate-100 bg-slate-50">
                                        {["User", "Email", "Role", "Status", ""].map(h => (
                                            <th key={h} className="text-left px-6 py-4 font-medium text-slate-400 text-xs uppercase tracking-wide">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    <AnimatePresence>
                                        {users.length === 0 ? (
                                            <tr><td colSpan={5} className="text-center py-16 text-slate-400">No users found</td></tr>
                                        ) : users.map((u, i) => (
                                            <motion.tr key={u.id}
                                                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                                transition={{ delay: i * 0.03 }}
                                                className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
                                                <td className="px-6 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${roleAvatar[u.role] || roleAvatar.STUDENT} flex items-center justify-center text-xs font-bold text-white font-heading shrink-0`}>
                                                            {u.first_name?.[0]}{u.last_name?.[0]}
                                                        </div>
                                                        <div>
                                                            <p className="text-slate-800 font-medium">{u.first_name} {u.last_name}</p>
                                                            <p className="text-slate-400 text-xs">@{u.username}</p>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 text-slate-600">{u.email}</td>
                                                <td className="px-6 py-4">
                                                    <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${roleBadge[u.role] || roleBadge.STUDENT}`}>{u.role}</span>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full ${u.is_active ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-500"}`}>
                                                        {u.is_active ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                                                        {u.is_active ? "Active" : "Inactive"}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 text-right">
                                                    <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                                                        onClick={() => toggleStatus(u.id, u.is_active)}
                                                        className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${u.is_active ? "bg-red-50 text-red-500 hover:bg-red-100" : "bg-emerald-50 text-emerald-600 hover:bg-emerald-100"}`}>
                                                        {u.is_active ? "Deactivate" : "Activate"}
                                                    </motion.button>
                                                </td>
                                            </motion.tr>
                                        ))}
                                    </AnimatePresence>
                                </tbody>
                            </table>

                            {total > 10 && (
                                <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100">
                                    <p className="text-xs text-slate-400">Showing {(page - 1) * 10 + 1}-{Math.min(page * 10, total)} of {total}</p>
                                    <div className="flex gap-2">
                                        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                                            className="p-2 rounded-lg bg-slate-100 text-slate-500 disabled:opacity-30 hover:bg-slate-200 transition-colors">
                                            <ChevronLeft className="w-4 h-4" />
                                        </button>
                                        <button onClick={() => setPage(p => p + 1)} disabled={page * 10 >= total}
                                            className="p-2 rounded-lg bg-slate-100 text-slate-500 disabled:opacity-30 hover:bg-slate-200 transition-colors">
                                            <ChevronRight className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </motion.div>
            </div>
        </div>
    );
}