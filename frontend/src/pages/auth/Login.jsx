import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import LoginForm from "../../components/forms/LoginForm";

export default function Login() {
    const { login }             = useAuth();
    const navigate              = useNavigate();
    const [form,    setForm]    = useState({ identifier: "", password: "", remember_me: false });
    const [error,   setError]   = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const role = await login(form);
            if (role === "admin")        navigate("/admin");
            else if (role === "teacher") navigate("/teacher/dashboard");
            else                         navigate("/student/dashboard");
        } catch (err) {
            setError(err?.error?.message || "Login failed.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-md space-y-6">
                <div className="text-center">
                    <h1 className="text-3xl font-bold text-gray-900">Trustworthy TA Agent</h1>
                    <p className="text-gray-500 text-sm mt-1">Sign in to your account</p>
                </div>

                <LoginForm
                    form={form}
                    setForm={setForm}
                    error={error}
                    loading={loading}
                    onSubmit={handleSubmit}
                />

                <div className="text-sm text-center space-y-1">
                    <Link to="/forgot-password" className="text-blue-600 hover:underline block">
                        Forgot Password?
                    </Link>
                    <p className="text-gray-500">
                        Don't have an account?{" "}
                        <Link to="/register" className="text-blue-600 hover:underline font-medium">
                            Register
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
}