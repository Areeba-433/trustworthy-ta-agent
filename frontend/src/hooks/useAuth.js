import { useAuthContext } from "../context/AuthContext";

export function useAuth() {
    const { user, token, login, logout, loading } = useAuthContext();
    return {
        user,
        token,
        login,
        logout,
        loading,
        isAuthenticated: !!token,
        isAdmin:         user?.role === "admin",
        isTeacher:       user?.role === "teacher",
        isStudent:       user?.role === "student",
    };
}