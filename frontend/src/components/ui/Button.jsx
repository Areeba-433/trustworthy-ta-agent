import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

export default function Button({ children, loading, variant = "primary", className = "", ...props }) {
    const variants = {
        primary: "bg-gradient-to-r from-indigo-600 to-blue-600 text-white shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40",
        outline: "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50",
        ghost:   "bg-slate-100 text-slate-600 hover:bg-slate-200",
    };
    return (
        <motion.button
            whileHover={{ scale: 1.015, y: -1 }}
            whileTap={{ scale: 0.98 }}
            transition={{ type: "spring", stiffness: 400, damping: 20 }}
            disabled={loading}
            className={`relative w-full py-3.5 rounded-xl font-semibold text-sm disabled:opacity-60 disabled:cursor-not-allowed transition-shadow ${variants[variant]} ${className}`}
            {...props}
        >
            <span className="flex items-center justify-center gap-2">
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                {children}
            </span>
        </motion.button>
    );
}