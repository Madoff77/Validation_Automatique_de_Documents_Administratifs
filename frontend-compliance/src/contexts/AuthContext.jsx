import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { authApi } from "@/api/index";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = localStorage.getItem("access_token");
        if (!token) {
            setLoading(false);
            return;
        }
        authApi.me()
            .then(setUser)
            .catch(() => {
                localStorage.clear();
                setUser(null);
            })
            .finally(() => setLoading(false));
    }, []);

    const login = useCallback(async (username, password) => {
        const data = await authApi.login(username, password);
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        const me = await authApi.me();
        setUser(me);
        return me;
    }, []);

    const logout = useCallback(async () => {
        try {
            const rt = localStorage.getItem("refresh_token");
            if (rt) await authApi.logout(rt);
        } catch (_) {}
        localStorage.clear();
        setUser(null);
    }, []);

    return (
        <AuthContext.Provider
            value={{
                user,
                loading,
                login,
                logout,
                isAdmin: user?.role === "admin",
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
};
