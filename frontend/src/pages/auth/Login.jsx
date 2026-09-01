import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export default function Login() {
    const { login }    = useAuth();
    const navigate     = useNavigate();
    const [form,    setForm]    = useState({ email_or_username: "", password: "", remember_me: false });
    const [error,   setError]   = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const role = await login(form);
            navigate(role === "admin" ? "/admin" : "/dashboard");
        } catch (err) {
            setError(err.detail || "Login failed. Check your credentials.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <form onSubmit={handleSubmit} className="bg-white p-8 rounded-xl shadow-md w-96 space-y-4">
                <h2 className="text-2xl font-bold text-center text-gray-800">Sign In</h2>

                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded px-3 py-2">
                        {error}
                    </div>
                )}

                <input
                    type="text"
                    placeholder="Email or Username"
                    required
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.email_or_username}
                    onChange={e => setForm({ ...form, email_or_username: e.target.value })}
                />
                <input
                    type="password"
                    placeholder="Password"
                    required
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.password}
                    onChange={e => setForm({ ...form, password: e.target.value })}
                />

                <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={form.remember_me}
                        onChange={e => setForm({ ...form, remember_me: e.target.checked })}
                        className="rounded"
                    />
                    Remember Me
                </label>

                <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition disabled:opacity-50 font-medium"
                >
                    {loading ? "Signing in..." : "Sign In"}
                </button>

                <div className="text-sm text-center space-y-1">
                    <Link to="/forgot-password" className="text-blue-500 hover:underline block">
                        Forgot Password?
                    </Link>
                    <Link to="/register" className="text-blue-500 hover:underline block">
                        Don't have an account? Register
                    </Link>
                </div>
            </form>
        </div>
    );
}