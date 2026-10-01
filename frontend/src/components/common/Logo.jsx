import { GraduationCap } from "lucide-react";

export default function Logo({ size = "md" }) {
    const sizes     = { sm: "w-8 h-8",  md: "w-10 h-10", lg: "w-14 h-14" };
    const iconSizes = { sm: 16,         md: 20,          lg: 28 };
    return (
        <div className="inline-flex items-center gap-2.5">
            <div className={`${sizes[size]} rounded-xl bg-gradient-to-br from-indigo-600 to-blue-500 flex items-center justify-center shadow-lg shadow-indigo-500/30`}>
                <GraduationCap className="text-white" size={iconSizes[size]} />
            </div>
            <span className="font-heading font-bold text-slate-800 text-lg">Trustworthy TA</span>
        </div>
    );
}