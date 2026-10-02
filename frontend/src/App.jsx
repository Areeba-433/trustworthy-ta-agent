import { Routes, Route } from "react-router-dom";
import Login          from "./pages/auth/Login";
import Register       from "./pages/auth/Register";
import VerifyEmail    from "./pages/auth/VerifyEmail";
import ForgotPassword from "./pages/auth/ForgotPassword";
import ResetPassword  from "./pages/auth/ResetPassword";
import Profile        from "./pages/user/Profile";
import EditProfile    from "./pages/user/EditProfile";
import UsersList      from "./pages/admin/UsersList";
import Unauthorized   from "./pages/Unauthorized";
import PrivateRoute   from "./components/common/PrivateRoute";

export default function App() {
  return (
    <Routes>
            <Route path="/login"           element={<Login />} />
            <Route path="/register"        element={<Register />} />
            <Route path="/verify-email"    element={<VerifyEmail />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password"  element={<ResetPassword />} />

            <Route path="/profile" element={<PrivateRoute><Profile /></PrivateRoute>} />
            <Route path="/profile/edit" element={<PrivateRoute><EditProfile /></PrivateRoute>} />
            <Route path="/admin/users" element={<PrivateRoute role="admin"><UsersList /></PrivateRoute>} />

            <Route path="/"             element={<Login />} />
            <Route path="/unauthorized" element={<Unauthorized />} />
    </Routes>
  );
}

