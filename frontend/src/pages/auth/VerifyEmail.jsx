import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { CheckCircle2, XCircle, MailCheck } from "lucide-react";
import { authService } from "../../services/auth";
import Background from "../../components/common/Background";
import Logo from "../../components/common/Logo";
import Button from "../../components/ui/Button";

export default function VerifyEmail() {
    const [searchParams] = useSearchParams();
    const token = searchParams.get("token");
    const [status, setStatus] = useState(token ? "confirm" : "error");
    const [message, setMessage] = useState(token ? "" : "Invalid verification link.");
    const [loading, setLoading] = useState(false);

    // Verification only happens when the user explicitly clicks the button
    // below - NOT automatically on page load. Auto-verifying on load means
    // a browser's link-preload feature, or an email security scanner that
    // "pre-clicks" links, can silently consume the token before the real
    // user ever sees this page.
    const handleVerify = () => {
        setLoading(true);
        authService.verifyEmail(token)
            .then(() => { setStatus("success"); setMessage("Your email has been verified. You can now sign in."); })
            .catch(err => { setStatus("error"); setMessage(err?.error?.message || "Verification failed or link expired."); })
            .finally(() => setLoading(false));
    };

    return (
        <div className="min-h-screen flex items-center justify-center px-4 relative">
            <Background />
            <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                className="w-full max-w-md"
            >
                <div className="flex justify-center mb-6"><Logo size="md" /></div>

                <div className="edu-card rounded-3xl p-10 text-center">
                    {status === "confirm" && (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-blue-500 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-indigo-500/25">
                                <MailCheck className="w-8 h-8 text-white" />
                            </div>
                            <h2 className="font-heading text-2xl font-bold text-slate-800 mb-2">Confirm your email</h2>
                            <p className="text-slate-500 text-sm mb-8">Click below to verify this address and activate your account.</p>
                            <Button type="button" loading={loading} onClick={handleVerify}>
                                {!loading && "Verify My Email"}
                            </Button>
                        </motion.div>
                    )}

                    {status === "success" && (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                            <motion.div
                                initial={{ scale: 0 }} animate={{ scale: 1 }}
                                transition={{ type: "spring", stiffness: 200 }}
                                className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-emerald-500/25"
                            >
                                <CheckCircle2 className="w-8 h-8 text-white" />
                            </motion.div>
                            <h2 className="font-heading text-2xl font-bold text-slate-800 mb-2">Email Verified!</h2>
                            <p className="text-slate-500 text-sm mb-8">{message}</p>
                            <Link to="/login"><Button type="button">Continue to Login</Button></Link>
                        </motion.div>
                    )}

                    {status === "error" && (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                            <motion.div
                                initial={{ scale: 0 }} animate={{ scale: 1 }}
                                transition={{ type: "spring", stiffness: 200 }}
                                className="w-16 h-16 rounded-2xl bg-gradient-to-br from-red-500 to-rose-500 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-red-500/25"
                            >
                                <XCircle className="w-8 h-8 text-white" />
                            </motion.div>
                            <h2 className="font-heading text-2xl font-bold text-slate-800 mb-2">Verification Failed</h2>
                            <p className="text-red-500 text-sm mb-8">{message}</p>
                            <Link to="/login">
                                <button className="bg-slate-100 hover:bg-slate-200 px-6 py-3 rounded-xl text-slate-600 text-sm font-medium transition-colors">
                                    Back to Login
                                </button>
                            </Link>
                        </motion.div>
                    )}
                </div>
            </motion.div>
        </div>
    );
}