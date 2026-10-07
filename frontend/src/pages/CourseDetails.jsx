import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, BookOpen, Hash, Calendar, Bot } from "lucide-react";
import {
  getCourse,
  getEnrolledCourse,
  getErrorMessage,
  isUnauthorized,
} from "../api/courses.js";
import { userService } from "../services/user";
import Background from "../components/common/Background";
import Logo from "../components/common/Logo";
import TaPanel from "../components/TaPanel.jsx";
import "./courses.css";

export default function CourseDetails() {
  const { courseId } = useParams();

  const [role, setRole] = useState(null);
  const [roleLoading, setRoleLoading] = useState(true);

  const [course, setCourse] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const isStudent = String(role || "").toUpperCase() === "STUDENT";

  useEffect(() => {
    userService
      .getProfile()
      .then((res) => {
        const r = res.data?.role ?? res.data?.data?.role ?? null;
        setRole(r);
      })
      .catch(() => setRole(null))
      .finally(() => setRoleLoading(false));
  }, []);

  useEffect(() => {
    if (roleLoading) return;
    if (!courseId || !role) return;

    let cancelled = false;
    const fetcher = isStudent ? getEnrolledCourse : getCourse;

    fetcher(courseId)
      .then((data) => {
        if (!cancelled) setCourse(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          isUnauthorized(err) ? "You are not logged in." : getErrorMessage(err)
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [courseId, role, roleLoading, isStudent]);

  return (
    <div className="min-h-screen px-4 py-12 relative">
      <Background />
      <div className="max-w-3xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between mb-8"
        >
          <Logo size="sm" />
          <Link
            to="/courses"
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition-colors bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            {isStudent ? "Back to My Classes" : "Back to My Courses"}
          </Link>
        </motion.div>

        {loading && (
          <div className="flex items-center justify-center py-16">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              className="w-10 h-10 border-4 border-indigo-100 border-t-indigo-600 rounded-full"
            />
          </div>
        )}

        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-2xl px-5 py-4">
            {error}
          </div>
        )}

        {course && (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="edu-card rounded-3xl overflow-hidden"
          >
            <div className="h-24 bg-gradient-to-br from-indigo-500 via-blue-500 to-indigo-400 relative">
              <div
                className="absolute inset-0 opacity-20"
                style={{
                  backgroundImage:
                    "radial-gradient(circle at 20% 50%, white 1px, transparent 1px)",
                  backgroundSize: "24px 24px",
                }}
              />
            </div>

            <div className="px-8 py-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center">
                  <BookOpen className="w-5 h-5 text-indigo-600" />
                </div>
                <h1 className="font-heading text-2xl font-bold text-slate-800">
                  {course.name}
                </h1>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-6">
                <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-white border border-slate-200 flex items-center justify-center shrink-0">
                    <Hash className="w-4 h-4 text-indigo-500" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-slate-400">Course Code</p>
                    <p className="text-sm text-slate-800 font-medium truncate">
                      {course.code || "—"}
                    </p>
                  </div>
                </div>

                <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-white border border-slate-200 flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4 text-indigo-500" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-slate-400">Teaching Assistant</p>
                    <p className="text-sm text-indigo-600 font-medium truncate">
                      {course.ta?.name || "—"}
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-4 bg-slate-50 border border-slate-100 rounded-xl p-4">
                <p className="text-xs text-slate-400 mb-1">Description</p>
                <p className="text-sm text-slate-700 whitespace-pre-line">
                  {course.description || "No description."}
                </p>
              </div>

              {course.created_at && (
                <div className="mt-4 bg-slate-50 border border-slate-100 rounded-xl p-4 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-white border border-slate-200 flex items-center justify-center shrink-0">
                    <Calendar className="w-4 h-4 text-indigo-500" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-slate-400">Created</p>
                    <p className="text-sm text-slate-800 font-medium truncate">
                      {new Date(course.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              )}

              <div className="mt-6 pt-6 border-t border-slate-100">
                <TaPanel
  courseId={courseId}
  isTeacher={!isStudent}
  initialTa={course.ta ?? null}
/>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}