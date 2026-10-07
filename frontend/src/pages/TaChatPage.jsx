import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Bot,
  MessageSquare,
  Sparkles,
  Lock,
} from "lucide-react";
import Background from "../components/common/Background";
import Logo from "../components/common/Logo";
import {
  getCourse,
  getEnrolledCourse,
  getErrorMessage,
  isUnauthorized,
} from "../api/courses.js";
import { userService } from "../services/user";
import "./courses.css";

export default function TaChatPage() {
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

  const ta = course?.ta;
  const taName = ta?.name || "your Teaching Assistant";

  // Access rule: teacher always, student only when ACTIVE.
  const taActive = ta?.status === "ACTIVE";
  const canChat = !!ta && (taActive || !isStudent);

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
            to={`/courses/${courseId}`}
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition-colors bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to course
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
          <>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05, duration: 0.4 }}
              className="mb-6"
            >
              <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">
                {course.name}
              </p>
              <h1 className="font-heading text-3xl font-bold text-slate-800 flex items-center gap-3">
                <Bot className="w-7 h-7 text-indigo-500" />
                {taName}
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                Chat with your AI Teaching Assistant about this course.
              </p>
            </motion.div>

            {/* No TA at all */}
            {!ta && (
              <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, duration: 0.4 }}
                className="edu-card rounded-3xl p-10 text-center"
              >
                <div className="w-16 h-16 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-center mx-auto mb-5">
                  <Bot className="w-8 h-8 text-slate-400" />
                </div>
                <h2 className="font-heading text-xl font-bold text-slate-800 mb-2">
                  No teaching assistant yet
                </h2>
                <p className="text-sm text-slate-500 max-w-md mx-auto">
                  Your teacher has not set up a teaching assistant for this
                  course yet.
                </p>
              </motion.div>
            )}

            {/* TA exists but not active, and viewer is a student */}
            {ta && !canChat && (
              <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, duration: 0.4 }}
                className="edu-card rounded-3xl p-10 text-center"
              >
                <div className="w-16 h-16 rounded-2xl bg-amber-50 border border-amber-100 flex items-center justify-center mx-auto mb-5">
                  <Lock className="w-8 h-8 text-amber-500" />
                </div>
                <h2 className="font-heading text-xl font-bold text-slate-800 mb-2">
                  {ta.status === "INACTIVE"
                    ? "Assistant is turned off"
                    : "Assistant is not ready yet"}
                </h2>
                <p className="text-sm text-slate-500 max-w-md mx-auto leading-relaxed">
                  {ta.status === "INACTIVE"
                    ? "Your teacher has turned off the assistant for this course."
                    : "Your teacher is still setting up the teaching assistant. It will become available once activated."}
                </p>
              </motion.div>
            )}

            {/* Ready (coming-soon for now) */}
            {canChat && (
              <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  delay: 0.15,
                  duration: 0.5,
                  ease: [0.22, 1, 0.36, 1],
                }}
                className="edu-card rounded-3xl overflow-hidden"
              >
                <div className="h-20 bg-gradient-to-br from-indigo-500 via-blue-500 to-indigo-400 relative">
                  <div
                    className="absolute inset-0 opacity-20"
                    style={{
                      backgroundImage:
                        "radial-gradient(circle at 20% 50%, white 1px, transparent 1px)",
                      backgroundSize: "24px 24px",
                    }}
                  />
                </div>

                <div className="px-8 py-10 text-center">
                  <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto mb-5">
                    <MessageSquare className="w-8 h-8 text-indigo-500" />
                  </div>
                  <h2 className="font-heading text-2xl font-bold text-slate-800 mb-2 flex items-center justify-center gap-2">
                    <Sparkles className="w-5 h-5 text-indigo-400" />
                    Coming soon
                  </h2>
                  <p className="text-sm text-slate-500 max-w-md mx-auto leading-relaxed">
                    You will soon be able to chat directly with{" "}
                    <span className="text-slate-700 font-medium">
                      {taName}
                    </span>{" "}
                    about this course — ask questions, get explanations, and
                    practise problems based on the material your teacher has
                    uploaded.
                  </p>

                  <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl mx-auto text-left">
                    <Feature
                      title="Ask questions"
                      body="Get instant answers about lecture topics."
                    />
                    <Feature
                      title="Explanations"
                      body="Step-by-step help on assignments and problems."
                    />
                    <Feature
                      title="Course material"
                      body="Answers grounded in your course content."
                    />
                  </div>

                  <p className="text-xs text-slate-400 mt-8">
                    This feature is under development. Check back soon.
                  </p>
                </div>
              </motion.div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Feature({ title, body }) {
  return (
    <div className="bg-slate-50 border border-slate-100 rounded-2xl p-4">
      <p className="font-heading text-sm font-bold text-slate-800">{title}</p>
      <p className="text-xs text-slate-500 mt-1 leading-relaxed">{body}</p>
    </div>
  );
}