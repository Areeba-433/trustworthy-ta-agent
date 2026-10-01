import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Mail, ArrowRight, ArrowLeft, MailCheck } from "lucide-react";
import { authService } from "../../services/auth";
import Background from "../../components/common/Background";
import Logo from "../../components/common/Logo";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";

export default function ForgotPassword() {
    const [email, setEmail] = useState("");
    const [sent, setSent]   = useState(false);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await authService.forgotPassword(email);
        } finally {
            setSent(true);
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
                <div className="flex justify-center mb-8"><Logo size="md" /></div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 }}
                    className="edu-card rounded-3xl p-8 overflow-hidden"
                >
                    {!sent ? (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                            <h1 className="font-heading text-2xl font-bold text-slate-800 mb-2">Forgot password?</h1>
                            <p className="text-slate-500 text-sm mb-8">No worries, we'll send you reset instructions.</p>
                            <form onSubmit={handleSubmit} className="space-y-5">
                                <Input icon={Mail} type="email" placeholder="your@email.com" required
                                    value={email} onChange={e => setEmail(e.target.value)} />
                                <Button type="submit" loading={loading}>
                                    {!loading && (<>Send Reset Link <ArrowRight className="w-4 h-4" /></>)}
                                </Button>
                            </form>
                        </motion.div>
                    ) : (
                        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center py-4">
                            <motion.div
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                transition={{ delay: 0.15, type: "spring", stiffness: 200 }}
                                className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-blue-500 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-indigo-500/25"
                            >
                                <MailCheck className="w-8 h-8 text-white" />
                            </motion.div>
                            <h2 className="font-heading text-xl font-bold text-slate-800 mb-2">Check your email</h2>
                            <p className="text-slate-500 text-sm">
                                If an account exists for <span className="text-slate-700 font-medium">{email}</span>, you'll receive reset instructions shortly.
                            </p>
                        </motion.div>
                    )}
                </motion.div>

                <Link to="/login" className="flex items-center justify-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mt-6 transition-colors">
                    <ArrowLeft className="w-3.5 h-3.5" /> Back to login
                </Link>
            </motion.div>
        </div>
    );
}