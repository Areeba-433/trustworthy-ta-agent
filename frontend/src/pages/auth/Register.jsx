import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import confetti from "canvas-confetti";
import { Mail, Lock, User, GraduationCap, BookOpen, ArrowRight, MailCheck } from "lucide-react";
import { authService } from "../../services/auth";
import Background from "../../components/common/Background";
import Logo from "../../components/common/Logo";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import Turnstile from "../../components/ui/Turnstile";

export default function Register() {
    const [step, setStep] = useState(1);
    const [form, setForm] = useState({
        email: "", username: "", password: "", confirm_password: "",
        first_name: "", last_name: "", role: "STUDENT"
    });
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);
    const [captchaToken, setCaptchaToken] = useState("");

    useEffect(() => {
        if (success) {
            confetti({
                particleCount: 100, spread: 70, origin: { y: 0.6 },
                colors: ['#6366f1', '#3b82f6', '#10b981', '#f59e0b'],
            });
        }
    }, [success]);

    const handleNext = (e) => { e.preventDefault(); setStep(2); };

    const handleBack = () => { setStep(1); setCaptchaToken(""); };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (form.password !== form.confirm_password) {
            toast.error("Passwords do not match");
            return;
        }
        if (!captchaToken) {
            toast.error("Please complete the CAPTCHA");
            return;
        }
        setLoading(true);
        try {
            await authService.register({ ...form, captcha_token: captchaToken });
            setSuccess(true);
            toast.success("Account created! \ud83c\udf89");
        } catch (err) {
            toast.error(err?.error?.message || "Registration failed");
            setCaptchaToken("");
        } finally {
            setLoading(false);
        }
    };

    if (success) {
        return (
            <div className="min-h-screen flex items-center justify-center px-4 relative">
                <Background />
                <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                    className="edu-card rounded-3xl p-10 max-w-md w-full text-center"
                >
                    <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                        className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-emerald-500/25"
                    >
                        <MailCheck className="w-8 h-8 text-white" />
                    </motion.div>
                    <h2 className="font-heading text-2xl font-bold text-slate-800 mb-2">Check your inbox</h2>
                    <p className="text-slate-500 text-sm mb-8">
                        We sent a verification link to <span className="text-slate-700 font-medium">{form.email}</span>.
                        Click it to activate your account.
                    </p>
                    <Link to="/login">
                        <Button type="button">Back to Login <ArrowRight className="w-4 h-4" /></Button>
                    </Link>
                </motion.div>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center px-4 py-12 relative">
            <Background />
            <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                className="w-full max-w-md"
            >
                <div className="text-center mb-6">
                    <div className="flex justify-center mb-6">
                        <Logo size="md" />
                    </div>
                    <h1 className="font-heading text-3xl font-bold text-slate-800 mb-2">Join the classroom </h1>
                    <p className="text-slate-500 text-sm">
                        Step {step} of 2 — {step === 1 ? "Your details" : "Secure your account"}
                    </p>
                </div>

                <div className="flex gap-2 mb-6">
                    {[1, 2].map(s => (
                        <div key={s} className="flex-1 h-1.5 rounded-full bg-slate-200 overflow-hidden">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: step >= s ? "100%" : "0%" }}
                                transition={{ duration: 0.4 }}
                                className="h-full bg-gradient-to-r from-indigo-500 to-blue-500"
                            />
                        </div>
                    ))}
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="edu-card rounded-3xl p-8 overflow-hidden"
                >
                    <AnimatePresence mode="wait">
                        {step === 1 ? (
                            <motion.form
                                key="step1"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ duration: 0.3 }}
                                onSubmit={handleNext}
                                className="space-y-4"
                            >
                                <div className="grid grid-cols-2 gap-3">
                                    <Input icon={User} placeholder="First name" required
                                        value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} />
                                    <Input icon={User} placeholder="Last name" required
                                        value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} />
                                </div>
                                <Input icon={Mail} type="email" placeholder="Email address" required
                                    value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
                                <Input icon={User} placeholder="Username" required
                                    value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} />

                                <div className="space-y-1.5">
                                    <label className="text-sm font-medium text-slate-700">I am a</label>
                                    <div className="grid grid-cols-2 gap-3">
                                        {[
                                            { val: "STUDENT", label: "Student", Icon: GraduationCap },
                                            { val: "TEACHER", label: "Teacher", Icon: BookOpen },
                                        ].map(({ val, label, Icon }) => (
                                            <button
                                                key={val}
                                                type="button"
                                                onClick={() => setForm({ ...form, role: val })}
                                                className={`flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-medium transition-all border-2 ${
                                                    form.role === val
                                                        ? "bg-indigo-50 border-indigo-400 text-indigo-700"
                                                        : "bg-slate-50 border-slate-200 text-slate-500 hover:border-slate-300"
                                                }`}
                                            >
                                                <Icon className="w-4 h-4" /> {label}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <Button type="submit">Continue <ArrowRight className="w-4 h-4" /></Button>
                            </motion.form>
                        ) : (
                            <motion.form
                                key="step2"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ duration: 0.3 }}
                                onSubmit={handleSubmit}
                                className="space-y-4"
                            >
                                <Input icon={Lock} type="password" placeholder="Password" required
                                    value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
                                <Input icon={Lock} type="password" placeholder="Confirm password" required
                                    value={form.confirm_password} onChange={e => setForm({ ...form, confirm_password: e.target.value })} />

                                <div className="flex gap-2 text-xs text-slate-500 flex-wrap">
                                    {["8+ characters", "Uppercase letter", "A number"].map(req => (
                                        <span key={req} className="px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200">
                                            {req}
                                        </span>
                                    ))}
                                </div>

                                <Turnstile onVerify={setCaptchaToken} onExpire={() => setCaptchaToken("")} />

                                <div className="flex gap-3 pt-2">
                                    <button type="button" onClick={handleBack}
                                        className="flex-1 py-3.5 rounded-xl text-sm font-medium text-slate-500 bg-slate-100 hover:bg-slate-200 transition-colors">
                                        Back
                                    </button>
                                    <div className="flex-1">
                                        <Button type="submit" loading={loading}>
                                            {!loading && "Create Account"}
                                        </Button>
                                    </div>
                                </div>
                            </motion.form>
                        )}
                    </AnimatePresence>
                </motion.div>

                <p className="text-center text-sm text-slate-500 mt-6">
                    Already have an account?{" "}
                    <Link to="/login" className="text-indigo-600 font-semibold hover:text-indigo-700 transition-colors">
                        Sign in
                    </Link>
                </p>
            </motion.div>
        </div>
    );
}
