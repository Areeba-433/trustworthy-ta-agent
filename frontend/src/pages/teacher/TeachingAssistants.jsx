import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, Plus, Pencil, Trash2, BookOpen, LogOut, UserCircle, X } from "lucide-react";
import toast from "react-hot-toast";
import { taService } from "../../services/teachingAssistants";
import { useAuth } from "../../context/AuthContext";
import Background from "../../components/common/Background";
import Logo from "../../components/common/Logo";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";

const STATUS_BADGE = {
    DRAFT:    "bg-amber-50 text-amber-600 border-amber-200",
    ACTIVE:   "bg-emerald-50 text-emerald-600 border-emerald-200",
    INACTIVE: "bg-slate-100 text-slate-500 border-slate-200",
};

const EMPTY_FORM = { name: "", description: "", status: "DRAFT" };

export default function TeachingAssistants() {
    const { logout } = useAuth();
    const [tas, setTas]           = useState([]);
    const [loading, setLoading]   = useState(true);
    const [formOpen, setFormOpen] = useState(false);
    const [editing, setEditing]   = useState(null);   // the TA being edited, or null when creating
    const [form, setForm]         = useState(EMPTY_FORM);
    const [saving, setSaving]     = useState(false);
    const [confirmId, setConfirmId] = useState(null); // id of the TA waiting for delete confirmation

    const loadTas = () =>
        taService.list()
            .then((res) => setTas(res.data?.teaching_assistants || []))
            .catch((err) => toast.error(err?.error?.message || "Failed to load teaching assistants"))
            .finally(() => setLoading(false));

    useEffect(() => { loadTas(); }, []);

    const openCreate = () => {
        setEditing(null);
        setForm(EMPTY_FORM);
        setFormOpen(true);
    };

    const openEdit = (ta) => {
        setEditing(ta);
        setForm({ name: ta.name, description: ta.description || "", status: ta.status });
        setFormOpen(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name.trim()) {
            toast.error("Name is required");
            return;
        }
        setSaving(true);
        try {
            const description = form.description.trim() || null;
            if (editing) {
                await taService.update(editing.id, { name: form.name, description, status: form.status });
                toast.success("Teaching assistant updated");
            } else {
                await taService.create({ name: form.name, description });
                toast.success("Teaching assistant created");
            }
            setFormOpen(false);
            loadTas();
        } catch (err) {
            toast.error(err?.error?.message || "Could not save");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id) => {
        try {
            await taService.remove(id);
            toast.success("Teaching assistant deleted");
            setConfirmId(null);
            loadTas();
        } catch (err) {
            toast.error(err?.error?.message || "Could not delete");
        }
    };

    return (
        <div className="min-h-screen px-4 py-12 relative">
            <Background />
            <div className="max-w-4xl mx-auto">
                <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between mb-8">
                    <Logo size="sm" />
                    <div className="flex items-center gap-2">
                        <Link to="/profile"
                            className="flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition-colors bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-sm">
                            <UserCircle className="w-4 h-4" /> Profile
                        </Link>
                        <button onClick={logout}
                            className="flex items-center gap-2 text-sm text-slate-500 hover:text-red-500 transition-colors bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-sm">
                            <LogOut className="w-4 h-4" /> Logout
                        </button>
                    </div>
                </motion.div>

                <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
                    <div>
                        <h1 className="font-heading text-2xl font-bold text-slate-800">My Teaching Assistants</h1>
                        <p className="text-sm text-slate-400 mt-1">Create an assistant once, then use it across your courses.</p>
                    </div>
                    <div className="w-44">
                        <Button onClick={openCreate}><Plus className="w-4 h-4" /> New assistant</Button>
                    </div>
                </div>

                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                            className="w-8 h-8 border-4 border-indigo-100 border-t-indigo-600 rounded-full"
                        />
                    </div>
                ) : tas.length === 0 ? (
                    <div className="edu-card rounded-2xl p-12 text-center">
                        <Bot className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                        <p className="text-slate-600 font-medium">No teaching assistants yet</p>
                        <p className="text-sm text-slate-400 mt-1">Create your first assistant to get started.</p>
                    </div>
                ) : (
                    <div className="grid gap-4 sm:grid-cols-2">
                        {tas.map((ta) => (
                            <motion.div key={ta.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="edu-card rounded-2xl p-5">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-blue-500 flex items-center justify-center shrink-0">
                                            <Bot className="w-5 h-5 text-white" />
                                        </div>
                                        <h2 className="font-heading font-semibold text-slate-800 truncate">{ta.name}</h2>
                                    </div>
                                    <span className={`text-xs px-2.5 py-1 rounded-full border font-medium shrink-0 ${STATUS_BADGE[ta.status] || STATUS_BADGE.DRAFT}`}>
                                        {ta.status}
                                    </span>
                                </div>

                                <p className="text-sm text-slate-500 mt-3 break-words">{ta.description || "No description"}</p>

                                <div className="mt-4">
                                    <p className="text-xs uppercase tracking-wide text-slate-400 font-medium mb-1.5">Assigned courses</p>
                                    {ta.assigned_courses?.length ? (
                                        <ul className="space-y-1">
                                            {ta.assigned_courses.map((course) => (
                                                <li key={course.id} className="flex items-center gap-2 text-sm text-slate-600">
                                                    <BookOpen className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                                                    <span className="truncate">{course.name}{course.code ? ` (${course.code})` : ""}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <p className="text-sm text-slate-400">Not assigned to any course</p>
                                    )}
                                </div>

                                <div className="flex items-center justify-end gap-2 mt-5 pt-4 border-t border-slate-100">
                                    {confirmId === ta.id ? (
                                        <>
                                            <span className="text-xs text-slate-500 mr-auto">Delete this assistant?</span>
                                            <button onClick={() => setConfirmId(null)}
                                                className="text-xs px-3 py-1.5 rounded-lg font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors">
                                                Cancel
                                            </button>
                                            <button onClick={() => handleDelete(ta.id)}
                                                className="text-xs px-3 py-1.5 rounded-lg font-medium bg-red-500 text-white hover:bg-red-600 transition-colors">
                                                Yes, delete
                                            </button>
                                        </>
                                    ) : (
                                        <>
                                            <button onClick={() => openEdit(ta)}
                                                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-colors">
                                                <Pencil className="w-3.5 h-3.5" /> Edit
                                            </button>
                                            <button onClick={() => setConfirmId(ta.id)}
                                                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium bg-red-50 text-red-500 hover:bg-red-100 transition-colors">
                                                <Trash2 className="w-3.5 h-3.5" /> Delete
                                            </button>
                                        </>
                                    )}
                                </div>
                            </motion.div>
                        ))}
                    </div>
                )}
            </div>

            <AnimatePresence>
                {formOpen && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="fixed inset-0 z-20 bg-slate-900/40 flex items-center justify-center px-4"
                        onClick={() => setFormOpen(false)}>
                        <motion.form initial={{ scale: 0.96, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.96, y: 10 }}
                            onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}
                            className="edu-card rounded-2xl p-6 w-full max-w-md space-y-4">
                            <div className="flex items-center justify-between">
                                <h2 className="font-heading text-lg font-bold text-slate-800">
                                    {editing ? "Edit teaching assistant" : "New teaching assistant"}
                                </h2>
                                <button type="button" onClick={() => setFormOpen(false)} aria-label="Close"
                                    className="text-slate-400 hover:text-slate-600 transition-colors">
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <Input label="Name" icon={Bot} type="text" placeholder="e.g. AI Assistant" maxLength={150} autoFocus
                                value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />

                            <div className="space-y-1.5">
                                <label htmlFor="ta-description" className="text-sm font-medium text-slate-700">Description</label>
                                <textarea id="ta-description" rows={3} maxLength={2000} placeholder="What does this assistant help with?"
                                    className="edu-input w-full px-4 py-3 rounded-xl text-slate-800 placeholder:text-slate-400 text-sm focus:outline-none resize-none"
                                    value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
                            </div>

                            {editing && (
                                <div className="space-y-1.5">
                                    <label htmlFor="ta-status" className="text-sm font-medium text-slate-700">Status</label>
                                    <select id="ta-status"
                                        className="edu-input w-full px-4 py-3 rounded-xl text-slate-800 text-sm focus:outline-none cursor-pointer"
                                        value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                                        <option value="DRAFT">Draft</option>
                                        <option value="ACTIVE">Active</option>
                                        <option value="INACTIVE">Inactive</option>
                                    </select>
                                </div>
                            )}

                            <Button type="submit" loading={saving}>{editing ? "Save changes" : "Create assistant"}</Button>
                        </motion.form>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}