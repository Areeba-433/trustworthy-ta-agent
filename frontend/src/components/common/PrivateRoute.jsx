import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../../context/AuthContext";
import Background from "./Background";

export default function PrivateRoute({ children, role }) {
    const { isAuthenticated, user, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center relative">
                <Background />
                <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    className="w-10 h-10 border-4 border-indigo-100 border-t-indigo-600 rounded-full"
                />
            </div>
        );
    }

    if (!isAuthenticated) return <Navigate to="/login" replace />;
    if (role && user?.role?.toLowerCase() !== role.toLowerCase()) {
        return <Navigate to="/unauthorized" replace />;
    }
    return children;
}