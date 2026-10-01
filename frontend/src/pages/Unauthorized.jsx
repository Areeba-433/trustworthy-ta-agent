import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ShieldAlert, ArrowLeft, Home } from "lucide-react";
import Background from "../components/common/Background";

export default function Unauthorized() {
    const navigate = useNavigate();
    return (
        <div className="min-h-screen flex items-center justify-center px-4 relative">
            <Background />
            <motion.div
                initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                className="edu-card rounded-3xl p-10 max-w-md w-full text-center"
            >
                <motion.div
                    initial={{ scale: 0, rotate: -10 }} animate={{ scale: 1, rotate: 0 }}
                    transition={{ delay: 0.15, type: "spring", stiffness: 200 }}
                    className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-orange-500/25"
                >
                    <ShieldAlert className="w-8 h-8 text-white" />
                </motion.div>
                <h1 className="font-heading text-2xl font-bold text-slate-800 mb-2">Access Denied</h1>
                <p className="text-slate-500 text-sm mb-8">
                    You don't have permission to view this page. Contact an administrator if you believe this is a mistake.
                </p>
                <div className="flex gap-3">
                    <button onClick={() => navigate(-1)}
                        className="flex-1 flex items-center justify-center gap-2 bg-slate-100 hover:bg-slate-200 py-3 rounded-xl text-slate-600 text-sm font-medium transition-colors">
                        <ArrowLeft className="w-4 h-4" /> Go Back
                    </button>
                    <Link to="/profile" className="flex-1">
                        <button className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-blue-600 py-3 rounded-xl text-white text-sm font-medium shadow-lg shadow-indigo-500/25">
                            <Home className="w-4 h-4" /> Home
                        </button>
                    </Link>
                </div>
            </motion.div>
        </div>
    );
}