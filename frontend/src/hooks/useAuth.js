import { useAuthContext } from "../context/AuthContext";

export function useAuth() {
    const { user, login, logout, loading, isAuthenticated } = useAuthContext();
    return {
        user, login, logout, loading, isAuthenticated,
        isAdmin:   user?.role === "admin",
        isTeacher: user?.role === "teacher",
        isStudent: user?.role === "student",
    };
}