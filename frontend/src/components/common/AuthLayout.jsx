import { motion } from "framer-motion";
import { GraduationCap } from "lucide-react";
import AnimatedBackground from "../three/AnimatedBackground";

export default function AuthLayout({ title, subtitle, children, footer }) {
    return (
        <div className="min-h-screen flex items-center justify-center px-4 py-12 relative">
            <AnimatedBackground />

            <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                className="w-full max-w-md"
            >
                <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.1, duration: 0.5 }}
                    className="text-center mb-8"
                >
                    <div className="inline-flex items-center gap-2 mb-4">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/30">
                            <GraduationCap className="w-5 h-5 text-white" />
                        </div>
                        <span className="font-display font-semibold text-white/90 text-lg">
                            Trustworthy TA
                        </span>
                    </div>
                    <h1 className="font-display text-3xl font-bold text-white mb-2">
                        {title}
                    </h1>
                    {subtitle && (
                        <p className="text-white/50 text-sm">{subtitle}</p>
                    )}
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2, duration: 0.5 }}
                    className="glass rounded-3xl p-8 shadow-2xl"
                >
                    {children}
                </motion.div>

                {footer && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.4 }}
                        className="text-center text-sm text-white/40 mt-6"
                    >
                        {footer}
                    </motion.div>
                )}
            </motion.div>
        </div>
    );
}
