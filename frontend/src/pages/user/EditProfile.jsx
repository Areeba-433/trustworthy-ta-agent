import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, Save, User, Phone, Building2, MapPin, FileText } from "lucide-react";
import toast from "react-hot-toast";
import { userService } from "../../services/user";
import { useAuth } from "../../context/AuthContext";
import Background from "../../components/common/Background";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";

export default function EditProfile() {
    const { user } = useAuth();
    const navigate  = useNavigate();
    const [form, setForm] = useState({
        first_name: "", last_name: "", phone_number: "",
        bio: "", department: "", city: "", country: "",
        semester: "", enrollment_year: "", cgpa: "",
    });
    const [loading, setLoading]   = useState(false);
    const [fetching, setFetching] = useState(true);

    useEffect(() => {
        userService.getProfile().then(res => {
            const d = res.data;
            setForm({
                first_name:      d.first_name               || "",
                last_name:       d.last_name                || "",
                phone_number:    d.profile?.phone_number    || "",
                bio:             d.profile?.bio             || "",
                department:      d.profile?.department      || "",
                city:            d.profile?.city            || "",
                country:         d.profile?.country         || "",
                semester:        d.profile?.semester        || "",
                enrollment_year: d.profile?.enrollment_year || "",
                cgpa:            d.profile?.cgpa            || "",
            });
        }).finally(() => setFetching(false));
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await userService.updateProfile(form);
            toast.success("Profile updated!");
            navigate("/profile");
        } catch (err) {
            toast.error(err?.error?.message || "Update failed");
        } finally {
            setLoading(false);
        }
    };

    if (fetching) {
        return (
            <div className="min-h-screen flex items-center justify-center relative">
                <Background />
                <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    className="w-10 h-10 border-4 border-indigo-100 border-t-indigo-600 rounded-full"
                />
            </div>
        );
    }

    return (
        <div className="min-h-screen px-4 py-12 relative">
            <Background />
            <div className="max-w-2xl mx-auto">
                <motion.button initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                    onClick={() => navigate("/profile")}
                    className="flex items-center gap-2 text-slate-500 hover:text-slate-700 text-sm mb-6 transition-colors">
                    <ArrowLeft className="w-4 h-4" /> Back to profile
                </motion.button>

                <motion.div
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                    className="edu-card rounded-3xl p-8"
                >
                    <h1 className="font-heading text-2xl font-bold text-slate-800 mb-1">Edit Profile</h1>
                    <p className="text-slate-500 text-sm mb-8">Update your personal information</p>

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div className="grid grid-cols-2 gap-4">
                            <Input icon={User} label="First Name" required
                                value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} />
                            <Input icon={User} label="Last Name" required
                                value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} />
                        </div>

                        <Input icon={Phone} label="Phone Number" type="tel"
                            value={form.phone_number} onChange={e => setForm({ ...form, phone_number: e.target.value })} />

                        <div className="space-y-1.5">
                            <label className="text-sm font-medium text-slate-700 flex items-center gap-1.5">
                                <FileText className="w-3.5 h-3.5" /> Bio
                            </label>
                            <textarea rows={3} placeholder="Tell us about yourself..."
                                className="edu-input w-full px-4 py-3.5 rounded-xl text-slate-800 placeholder:text-slate-400 text-sm focus:outline-none resize-none"
                                value={form.bio} onChange={e => setForm({ ...form, bio: e.target.value })} />
                        </div>

                        <Input icon={Building2} label="Department"
                            value={form.department} onChange={e => setForm({ ...form, department: e.target.value })} />

                        <div className="grid grid-cols-2 gap-4">
                            <Input icon={MapPin} label="City"
                                value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} />
                            <Input icon={MapPin} label="Country"
                                value={form.country} onChange={e => setForm({ ...form, country: e.target.value })} />
                        </div>

                        {user?.role === "STUDENT" && (
                            <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-100">
                                <Input label="Semester" type="number"
                                    value={form.semester} onChange={e => setForm({ ...form, semester: e.target.value })} />
                                <Input label="Enroll Year" type="number"
                                    value={form.enrollment_year} onChange={e => setForm({ ...form, enrollment_year: e.target.value })} />
                                <Input label="CGPA" type="number" step="0.01"
                                    value={form.cgpa} onChange={e => setForm({ ...form, cgpa: e.target.value })} />
                            </div>
                        )}

                        <div className="flex gap-3 pt-2">
                            <button type="button" onClick={() => navigate("/profile")}
                                className="flex-1 py-3.5 rounded-xl text-sm font-medium text-slate-500 bg-slate-100 hover:bg-slate-200 transition-colors">
                                Cancel
                            </button>
                            <div className="flex-1">
                                <Button type="submit" loading={loading}>
                                    {!loading && (<><Save className="w-4 h-4" /> Save Changes</>)}
                                </Button>
                            </div>
                        </div>
                    </form>
                </motion.div>
            </div>
        </div>
    );
}