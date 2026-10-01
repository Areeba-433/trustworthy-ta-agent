import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { Mail, Lock, ArrowRight } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import Background from "../../components/common/Background";
import Logo from "../../components/common/Logo";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";

export default function Login() {
    const { login } = useAuth();
    const navigate   = useNavigate();
    const [form,    setForm]    = useState({ identifier: "", password: "", remember_me: false });
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const role = await login(form);
            toast.success("Welcome back! 🎓");
            navigate(role?.toLowerCase() === "admin" ? "/admin/users" : "/profile");
        } catch (err) {
            toast.error(err?.error?.message || "Login failed");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center px-4 py-12 relative">
            <Background />
            <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                className="w-full max-w-md"
            >
                <div className="text-center mb-8">
                    <div className="flex justify-center mb-6">
                        <Logo size="md" />
                    </div>
                    <h1 className="font-heading text-3xl font-bold text-slate-800 mb-2">Welcome back </h1>
                    <p className="text-slate-500 text-sm">Sign in to continue learning</p>
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 }}
                    className="edu-card rounded-3xl p-8"
                >
                    <form onSubmit={handleSubmit} className="space-y-5">
                        <Input
                            icon={Mail} type="text" placeholder="Email or username" required
                            value={form.identifier}
                            onChange={e => setForm({ ...form, identifier: e.target.value })}
                        />
                        <Input
                            icon={Lock} type="password" placeholder="Password" required
                            value={form.password}
                            onChange={e => setForm({ ...form, password: e.target.value })}
                        />

                        <div className="flex items-center justify-between text-sm">
                            <label className="flex items-center gap-2 text-slate-500 cursor-pointer select-none">
                                <input
                                    type="checkbox"
                                    checked={form.remember_me}
                                    onChange={e => setForm({ ...form, remember_me: e.target.checked })}
                                    className="w-4 h-4 rounded border-slate-300 accent-indigo-600"
                                />
                                Remember me
                            </label>
                            <Link to="/forgot-password" className="text-indigo-600 hover:text-indigo-700 font-medium transition-colors">
                                Forgot password?
                            </Link>
                        </div>

                        <Button type="submit" loading={loading}>
                            {!loading && (<>Sign In <ArrowRight className="w-4 h-4" /></>)}
                        </Button>
                    </form>
                </motion.div>

                <p className="text-center text-sm text-slate-500 mt-6">
                    New here?{" "}
                    <Link to="/register" className="text-indigo-600 font-semibold hover:text-indigo-700 transition-colors">
                        Create an account
                    </Link>
                </p>
            </motion.div>
        </div>
    );
}