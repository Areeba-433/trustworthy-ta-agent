import { motion } from "framer-motion";

export default function Input({ icon: Icon, label, error, ...props }) {
    return (
        <div className="space-y-1.5">
            {label && <label className="text-sm font-medium text-slate-700">{label}</label>}
            <div className="relative">
                {Icon && <Icon className="absolute left-4 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-slate-400" size={18} />}
                <motion.input
                    whileFocus={{ scale: 1.01 }}
                    className={`edu-input w-full ${Icon ? "pl-11" : "pl-4"} pr-4 py-3.5 rounded-xl text-slate-800 placeholder:text-slate-400 text-sm focus:outline-none transition-all`}
                    {...props}
                />
            </div>
            {error && <p className="text-xs text-red-500">{error}</p>}
        </div>
    );
}