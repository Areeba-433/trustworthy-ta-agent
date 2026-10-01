import { useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { Lock, ArrowRight, ArrowLeft, KeyRound } from "lucide-react";
import { authService } from "../../services/auth";
import Background from "../../components/common/Background";
import Logo from "../../components/common/Logo";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";

export default function ResetPassword() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const [form, setForm] = useState({ password: "", confirm_password: "" });
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (form.password !== form.confirm_password) {
            toast.error("Passwords do not match");
            return;
        }
        setLoading(true);
        try {
            await authService.resetPassword({ token: searchParams.get("token"), new_password: form.password });
            toast.success("Password reset successful!");
            navigate("/login");
        } catch (err) {
            toast.error(err?.error?.message || "Reset failed. Link may be expired.");
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
                    <div className="flex justify-center mb-6"><Logo size="md" /></div>
                    <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto mb-4">
                        <KeyRound className="w-7 h-7 text-indigo-600" />
                    </div>
                    <h1 className="font-heading text-2xl font-bold text-slate-800 mb-2">Reset password</h1>
                    <p className="text-slate-500 text-sm">Create a new, strong password</p>
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 }}
                    className="edu-card rounded-3xl p-8"
                >
                    <form onSubmit={handleSubmit} className="space-y-5">
                        <Input icon={Lock} type="password" placeholder="New password" required
                            value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
                        <Input icon={Lock} type="password" placeholder="Confirm new password" required
                            value={form.confirm_password} onChange={e => setForm({ ...form, confirm_password: e.target.value })} />

                        <div className="flex gap-2 text-xs text-slate-500 flex-wrap">
                            {["8+ characters", "Uppercase letter", "A number"].map(req => (
                                <span key={req} className="px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200">{req}</span>
                            ))}
                        </div>

                        <Button type="submit" loading={loading}>
                            {!loading && (<>Reset Password <ArrowRight className="w-4 h-4" /></>)}
                        </Button>
                    </form>
                </motion.div>

                <Link to="/login" className="flex items-center justify-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mt-6 transition-colors">
                    <ArrowLeft className="w-3.5 h-3.5" /> Back to login
                </Link>
            </motion.div>
        </div>
    );
}