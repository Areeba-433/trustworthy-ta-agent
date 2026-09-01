import { createContext, useContext, useState, useEffect } from "react";
import { authService } from "../services/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user,    setUser]    = useState(null);
    const [token,   setToken]   = useState(localStorage.getItem("access_token"));
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (token) {
            authService.getMe(token)
                .then(setUser)
                .catch(() => {
                    setToken(null);
                    localStorage.removeItem("access_token");
                    localStorage.removeItem("refresh_token");
                })
                .finally(() => setLoading(false));
        } else {
            setLoading(false);
        }
    }, [token]);

    const login = async (credentials) => {
        const data = await authService.login(credentials);
        localStorage.setItem("access_token",  data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        setToken(data.access_token);
        setUser(data.user);
        return data.role;
    };

    const logout = async () => {
        await authService.logout(token);
        localStorage.clear();
        setToken(null);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, token, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuthContext = () => useContext(AuthContext);