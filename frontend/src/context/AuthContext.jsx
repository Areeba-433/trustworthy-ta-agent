import { createContext, useContext, useState, useEffect } from "react";
import { authService } from "../services/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user,    setUser]    = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        authService.getMe()
            .then(res => setUser(res.data))
            .catch(() => setUser(null))
            .finally(() => setLoading(false));
    }, []);

    const login = async (credentials) => {
        const res = await authService.login(credentials);
        setUser(res.data.user);
        return res.data.user.role;
    };

    const logout = async () => {
        await authService.logout();
        setUser(null);
    };

    const roleLower = user?.role?.toLowerCase();

    return (
        <AuthContext.Provider value={{
            user, loading, login, logout,
            isAuthenticated: !!user,
            isAdmin:   roleLower === "admin",
            isTeacher: roleLower === "teacher",
            isStudent: roleLower === "student",
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);