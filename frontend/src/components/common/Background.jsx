import { motion } from "framer-motion";
import { BookOpen, GraduationCap, Lightbulb, PenTool, Sparkles } from "lucide-react";

const floatingIcons = [
    { Icon: GraduationCap, top: "12%", left: "8%",  delay: 0,   color: "text-indigo-300" },
    { Icon: BookOpen,      top: "22%", left: "88%", delay: 0.5, color: "text-amber-300" },
    { Icon: Lightbulb,     top: "72%", left: "6%",  delay: 1,   color: "text-emerald-300" },
    { Icon: PenTool,       top: "80%", left: "90%", delay: 1.5, color: "text-blue-300" },
    { Icon: Sparkles,      top: "45%", left: "94%", delay: 0.8, color: "text-purple-300" },
];

export default function Background() {
    return (
        <div className="fixed inset-0 -z-10 overflow-hidden bg-slate-50">
            <div className="absolute top-[-10%] left-[-5%] w-[500px] h-[500px] bg-indigo-200/50 rounded-full blur-[100px] animate-blob" />
            <div className="absolute bottom-[-10%] right-[-5%] w-[450px] h-[450px] bg-amber-200/40 rounded-full blur-[100px] animate-blob animation-delay-2000" />
            <div className="absolute top-[30%] right-[10%] w-[350px] h-[350px] bg-emerald-200/40 rounded-full blur-[100px] animate-blob animation-delay-4000" />

            <div className="absolute inset-0 opacity-40" style={{
                backgroundImage: 'linear-gradient(#e2e8f0 1px, transparent 1px), linear-gradient(90deg, #e2e8f0 1px, transparent 1px)',
                backgroundSize: '48px 48px'
            }} />

            {floatingIcons.map(({ Icon, top, left, delay, color }, i) => (
                <motion.div
                    key={i}
                    className={`absolute ${color} opacity-40 hidden md:block`}
                    style={{ top, left }}
                    animate={{ y: [0, -20, 0], rotate: [0, 8, 0] }}
                    transition={{ duration: 6, repeat: Infinity, delay, ease: "easeInOut" }}
                >
                    <Icon size={48} strokeWidth={1.5} />
                </motion.div>
            ))}
        </div>
    );
}