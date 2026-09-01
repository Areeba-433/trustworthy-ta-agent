import { Navigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export default function PrivateRoute({ children }) {
    const { isAuthenticated, loading } = useAuth();
    if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;
    return isAuthenticated ? children : <Navigate to="/login" replace />;
}