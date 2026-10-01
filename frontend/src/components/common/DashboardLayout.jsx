import { Link, useNavigate } from "react-router-dom";
import { GraduationCap, LogOut, BookOpen, Users, UserCircle } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import AnimatedBackground from "../three/AnimatedBackground";

export default function DashboardLayout({ children, title, subtitle }) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    const roleLabel = {
        STUDENT: "Student",
        TEACHER: "Teacher",
        ADMIN: "Administrator",
    }[user?.role] ?? user?.role;

    return (
        <div className="min-h-screen relative">
            <AnimatedBackground />

            <header className="relative z-10 border-b border-white/10 glass">
                <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                            <GraduationCap className="w-4.5 h-4.5 text-white" size={18} />
                        </div>
                        <div>
                            <p className="font-display font-semibold text-white text-sm">Trustworthy TA</p>
                            <p className="text-xs text-white/40">Educational Assistant Platform</p>
                        </div>
                    </div>

                    <nav className="flex items-center gap-2">
                        <Link
                            to="/profile"
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                        >
                            <UserCircle size={16} />
                            Profile
                        </Link>
                        {user?.role === "ADMIN" && (
                            <Link
                                to="/admin/users"
                                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                            >
                                <Users size={16} />
                                Users
                            </Link>
                        )}
                        <button
                            type="button"
                            onClick={handleLogout}
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-pink-300/80 hover:text-pink-200 hover:bg-white/5 transition-colors"
                        >
                            <LogOut size={16} />
                            Logout
                        </button>
                    </nav>
                </div>
            </header>

            <main className="relative z-10 max-w-5xl mx-auto px-4 py-10">
                <div className="mb-8">
                    <div className="flex items-center gap-2 mb-2">
                        <BookOpen className="w-5 h-5 text-indigo-400" />
                        <span className="text-xs uppercase tracking-wider text-indigo-300/80 font-medium">
                            {roleLabel}
                        </span>
                    </div>
                    <h1 className="font-display text-2xl font-bold text-white">{title}</h1>
                    {subtitle && <p className="text-white/50 text-sm mt-1">{subtitle}</p>}
                </div>
                {children}
            </main>
        </div>
    );
}
