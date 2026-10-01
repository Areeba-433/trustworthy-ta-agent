import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Mail, AtSign, Building2, Phone, MapPin, Edit3, LogOut, GraduationCap, BadgeCheck, Camera } from "lucide-react";
import toast from "react-hot-toast";
import { userService } from "../../services/user";
import { useAuth } from "../../context/AuthContext";
import Background from "../../components/common/Background";
import Logo from "../../components/common/Logo";

export default function Profile() {
    const { logout } = useAuth();
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [uploadingAvatar, setUploadingAvatar] = useState(false);

    useEffect(() => {
        userService.getProfile()
            .then(res => setProfile(res.data))
            .catch(() => toast.error("Failed to load profile"))
            .finally(() => setLoading(false));
    }, []);

    const handleLogout = async () => {
        await logout();
        toast.success("Logged out");
    };

    const handleAvatarChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploadingAvatar(true);
        try {
            const res = await userService.uploadAvatar(file);
            setProfile(prev => ({ ...prev, profile: { ...prev.profile, profile_picture_url: res.data.profile_picture_url } }));
            toast.success("Avatar updated!");
        } catch (err) {
            toast.error(err?.error?.message || "Upload failed");
        } finally {
            setUploadingAvatar(false);
        }
    };

    if (loading) {
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

    const infoItems = [
        { icon: Mail,      label: "Email",      value: profile?.email },
        { icon: AtSign,    label: "Username",   value: profile?.username },
        { icon: Building2, label: "Department", value: profile?.profile?.department },
        { icon: Phone,     label: "Phone",      value: profile?.profile?.phone_number },
        { icon: MapPin,    label: "Location",   value: profile?.profile?.city },
    ].filter(item => item.value);

    return (
        <div className="min-h-screen px-4 py-12 relative">
            <Background />
            <div className="max-w-3xl mx-auto">
                <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between mb-8">
                    <Logo size="sm" />
                    <button onClick={handleLogout}
                        className="flex items-center gap-2 text-sm text-slate-500 hover:text-red-500 transition-colors bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-sm">
                        <LogOut className="w-4 h-4" /> Logout
                    </button>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                    className="edu-card rounded-3xl overflow-hidden"
                >
                    <div className="h-32 bg-gradient-to-br from-indigo-500 via-blue-500 to-indigo-400 relative">
                        <div className="absolute inset-0 opacity-20" style={{
                            backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px)',
                            backgroundSize: '24px 24px'
                        }} />
                    </div>

                    <div className="px-8 pb-8">
                        <motion.div
                            initial={{ scale: 0 }} animate={{ scale: 1 }}
                            transition={{ delay: 0.3, type: "spring", stiffness: 200 }}
                            className="relative z-10 w-24 h-24 -mt-12 mb-4 group"
                        >
                            <label className="block w-full h-full rounded-2xl overflow-hidden cursor-pointer shadow-xl border-4 border-white">
                                {profile?.profile?.profile_picture_url ? (
                                    <img
                                        src={`${import.meta.env.VITE_API_URL || "http://localhost:8000"}${profile.profile.profile_picture_url}`}
                                        alt="avatar" className="w-full h-full object-cover"
                                    />
                                ) : (
                                    <div className="w-full h-full bg-gradient-to-br from-indigo-500 to-blue-500 flex items-center justify-center text-3xl font-bold text-white font-heading">
                                        {profile?.first_name?.[0]}{profile?.last_name?.[0]}
                                    </div>
                                )}
                                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                    <Camera className="w-6 h-6 text-white" />
                                </div>
                                <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
                                    onChange={handleAvatarChange} disabled={uploadingAvatar} />
                            </label>
                            {uploadingAvatar && (
                                <div className="absolute inset-0 rounded-2xl bg-black/50 flex items-center justify-center">
                                    <motion.div
                                        animate={{ rotate: 360 }}
                                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                                        className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full"
                                    />
                                </div>
                            )}
                        </motion.div>

                        <div className="flex items-start justify-between mb-6">
                            <div>
                                <h1 className="font-heading text-2xl font-bold text-slate-800 flex items-center gap-2">
                                    {profile?.first_name} {profile?.last_name}
                                    <BadgeCheck className="w-5 h-5 text-indigo-500" />
                                </h1>
                                <div className="flex items-center gap-2 mt-1">
                                    <GraduationCap className="w-4 h-4 text-slate-400" />
                                    <span className="text-sm text-slate-500 capitalize">{profile?.role?.toLowerCase()}</span>
                                </div>
                            </div>
                            <Link to="/profile/edit">
                                <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                                    className="flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-blue-600 text-white text-sm font-medium px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-500/25">
                                    <Edit3 className="w-4 h-4" /> Edit
                                </motion.button>
                            </Link>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {infoItems.map((item, i) => (
                                <motion.div key={item.label}
                                    initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.4 + i * 0.05 }}
                                    className="bg-slate-50 border border-slate-100 rounded-xl p-4 flex items-center gap-3">
                                    <div className="w-9 h-9 rounded-lg bg-white border border-slate-200 flex items-center justify-center shrink-0">
                                        <item.icon className="w-4 h-4 text-indigo-500" />
                                    </div>
                                    <div className="min-w-0">
                                        <p className="text-xs text-slate-400">{item.label}</p>
                                        <p className="text-sm text-slate-800 font-medium truncate">{item.value}</p>
                                    </div>
                                </motion.div>
                            ))}
                        </div>

                        {profile?.role === "STUDENT" && (profile?.profile?.semester || profile?.profile?.cgpa) && (
                            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}
                                className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-slate-100">
                                {[
                                    ["Semester", profile?.profile?.semester],
                                    ["Enrollment", profile?.profile?.enrollment_year],
                                    ["CGPA", profile?.profile?.cgpa],
                                ].filter(([, v]) => v).map(([label, val]) => (
                                    <div key={label} className="text-center bg-indigo-50 rounded-xl py-3">
                                        <p className="font-heading text-xl font-bold text-indigo-600">{val}</p>
                                        <p className="text-xs text-slate-500 mt-0.5">{label}</p>
                                    </div>
                                ))}
                            </motion.div>
                        )}
                    </div>
                </motion.div>
            </div>
        </div>
    );
}