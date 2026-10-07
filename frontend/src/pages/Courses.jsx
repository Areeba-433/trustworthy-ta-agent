import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  BookOpen,
  Plus,
  ArrowRight,
  KeyRound,
  Copy,
  Check,
  BookMarked,
} from "lucide-react";
import toast from "react-hot-toast";
import {
  createCourse,
  getErrorMessage,
  isUnauthorized,
  listCourses,
  joinCourseByCode,
  listMyEnrolledCourses,
} from "../api/courses.js";
import { userService } from "../services/user";
import Background from "../components/common/Background";
import Logo from "../components/common/Logo";
import "./courses.css";

export default function Courses() {
  const [role, setRole] = useState(null);
  const [roleLoading, setRoleLoading] = useState(true);

  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [needsLogin, setNeedsLogin] = useState(false);

  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const [joinCode, setJoinCode] = useState("");
  const [joining, setJoining] = useState(false);
  const [enrolled, setEnrolled] = useState([]);
  const [enrolledLoading, setEnrolledLoading] = useState(true);

  const [copiedId, setCopiedId] = useState(null);

  const upperRole = (role || "").toUpperCase();
  const isStudent = upperRole === "STUDENT";
  const isTeacher = upperRole === "TEACHER" || upperRole === "ADMIN";

  // 1) who am I
  useEffect(() => {
    userService
      .getProfile()
      .then((res) => {
        const r = res.data?.role ?? res.data?.data?.role ?? null;
        console.log("[Courses] detected role:", r);
        setRole(r);
      })
      .catch((err) => {
        console.warn("[Courses] profile fetch failed:", err?.message);
        setRole(null);
      })
      .finally(() => setRoleLoading(false));
  }, []);

  // 2) teacher: load my courses
  useEffect(() => {
    if (roleLoading) return;
    if (!isTeacher) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    listCourses()
      .then((data) => {
        if (!cancelled) setCourses(data);
      })
      .catch((err) => {
        if (cancelled) return;
        if (isUnauthorized(err)) setNeedsLogin(true);
        else setLoadError(getErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [roleLoading, isTeacher]);

  // 3) student: load enrolled courses
  useEffect(() => {
    if (roleLoading) return;
    if (!isStudent) {
      setEnrolledLoading(false);
      return;
    }
    let cancelled = false;
    listMyEnrolledCourses()
      .then((data) => {
        if (!cancelled) setEnrolled(data);
      })
      .catch(() => {
        if (!cancelled) setEnrolled([]);
      })
      .finally(() => {
        if (!cancelled) setEnrolledLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [roleLoading, isStudent]);

  async function handleCreate(e) {
    e.preventDefault();
    setFormError("");
    if (!name.trim()) {
      setFormError("Course name is required.");
      return;
    }
    setSaving(true);
    try {
      const created = await createCourse({
        name: name.trim(),
        code: code.trim() || null,
        description: description.trim() || null,
      });
      setCourses((prev) => [created, ...prev]);
      setName("");
      setCode("");
      setDescription("");
      toast.success("Course created");
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleJoin(e) {
    e.preventDefault();
    const trimmed = joinCode.trim().toUpperCase();
    if (!trimmed) {
      toast.error("Please enter a class code.");
      return;
    }
    setJoining(true);
    try {
      await joinCourseByCode(trimmed);
      toast.success("Joined class");
      setJoinCode("");
      const fresh = await listMyEnrolledCourses();
      setEnrolled(fresh);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setJoining(false);
    }
  }

  async function handleCopyJoinCode(course) {
    try {
      await navigator.clipboard.writeText(course.join_code);
      setCopiedId(course.id);
      toast.success("Join code copied");
      setTimeout(() => setCopiedId(null), 1500);
    } catch {
      toast.error("Could not copy");
    }
  }

  // ---------- render ----------

  if (roleLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center relative">
        <Background />
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-10 h-10 border-4 border-indigo-100 border-t-indigo-600 rounded-full"
        />
      </div>
    );
  }

  if (needsLogin) {
    return (
      <div className="min-h-screen px-4 py-12 relative">
        <Background />
        <div className="max-w-3xl mx-auto">
          <div className="edu-card rounded-3xl p-8 text-center">
            <p className="text-slate-600">
              You are not logged in.{" "}
              <Link
                to="/login"
                className="text-indigo-600 font-medium hover:text-indigo-700"
              >
                Go to login
              </Link>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ---------- STUDENT VIEW ----------
  if (isStudent) {
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
              to="/profile"
              className="flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition-colors bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-sm"
            >
              Back to Profile
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05, duration: 0.4 }}
            className="mb-6"
          >
            <h1 className="font-heading text-3xl font-bold text-slate-800 flex items-center gap-3">
              <BookMarked className="w-7 h-7 text-indigo-500" />
              My Classes
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Join a class using the code your teacher shared.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
            className="edu-card rounded-3xl p-6 mb-6"
          >
            <h2 className="font-heading text-lg font-semibold text-slate-800 flex items-center gap-2 mb-4">
              <KeyRound className="w-5 h-5 text-indigo-500" />
              Join a Class
            </h2>

            <form onSubmit={handleJoin} className="grid gap-3">
              <input
                type="text"
                placeholder="Enter class code (e.g. ABC123)"
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                maxLength={12}
                className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 tracking-[0.3em] uppercase focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 transition font-mono"
              />
              <div>
                <motion.button
                  whileHover={{ scale: joining ? 1 : 1.03 }}
                  whileTap={{ scale: joining ? 1 : 0.97 }}
                  type="submit"
                  disabled={joining}
                  className="inline-flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-blue-600 text-white text-sm font-medium px-6 py-3 rounded-xl shadow-lg shadow-indigo-500/25 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <ArrowRight className="w-4 h-4" />
                  {joining ? "Joining..." : "Join Class"}
                </motion.button>
              </div>
            </form>
          </motion.div>

          <motion.h2
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15 }}
            className="font-heading text-lg font-semibold text-slate-700 mb-3"
          >
            Enrolled Classes
          </motion.h2>

          {enrolledLoading && (
            <div className="edu-card rounded-3xl p-8 text-center text-slate-500 text-sm">
              Loading...
            </div>
          )}

          {!enrolledLoading && enrolled.length === 0 && (
            <div className="edu-card rounded-3xl p-8 text-center text-slate-500 text-sm">
              You have not joined any classes yet.
            </div>
          )}

          <div className="grid gap-4">
            {enrolled.map((c, i) => (
              <motion.div
                key={c.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.05, duration: 0.35 }}
                className="edu-card rounded-3xl p-6"
              >
                <h3 className="font-heading text-lg font-bold text-slate-800">
                  {c.name}
                </h3>
                {c.code && (
                  <p className="text-sm text-indigo-500 font-medium mt-0.5">
                    {c.code}
                  </p>
                )}
                {c.description && (
                  <p className="text-sm text-slate-600 mt-2">{c.description}</p>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ---------- TEACHER / ADMIN VIEW ----------
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center relative">
        <Background />
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-10 h-10 border-4 border-indigo-100 border-t-indigo-600 rounded-full"
        />
      </div>
    );
  }

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
            to="/profile"
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition-colors bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-sm"
          >
            Back to Profile
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05, duration: 0.4 }}
          className="mb-6"
        >
          <h1 className="font-heading text-3xl font-bold text-slate-800 flex items-center gap-3">
            <BookOpen className="w-7 h-7 text-indigo-500" />
            My Courses
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Create and manage the courses you teach.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.4 }}
          className="edu-card rounded-3xl p-6 mb-6"
        >
          <h2 className="font-heading text-lg font-semibold text-slate-800 flex items-center gap-2 mb-4">
            <Plus className="w-5 h-5 text-indigo-500" />
            Create Course
          </h2>

          <form onSubmit={handleCreate} className="courses-form grid gap-3">
            <input
              type="text"
              placeholder="Course name (required)"
              value={name}
              maxLength={150}
              onChange={(e) => setName(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 transition"
            />
            <input
              type="text"
              placeholder="Course code (optional, e.g. AI-101)"
              value={code}
              maxLength={20}
              onChange={(e) => setCode(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 transition"
            />
            <textarea
              placeholder="Description (optional)"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 transition resize-none"
            />

            {formError && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-2">
                {formError}
              </div>
            )}

            <div>
              <motion.button
                whileHover={{ scale: saving ? 1 : 1.03 }}
                whileTap={{ scale: saving ? 1 : 0.97 }}
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-blue-600 text-white text-sm font-medium px-6 py-3 rounded-xl shadow-lg shadow-indigo-500/25 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                <Plus className="w-4 h-4" />
                {saving ? "Creating..." : "Create Course"}
              </motion.button>
            </div>
          </form>
        </motion.div>

        {loadError && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-2xl px-5 py-4 mb-6">
            {loadError}
          </div>
        )}

        {!loadError && courses.length === 0 && (
          <div className="edu-card rounded-3xl p-8 text-center text-slate-500 text-sm">
            No courses yet. Create your first one above.
          </div>
        )}

        <div className="grid gap-4">
          {courses.map((course, i) => (
            <motion.div
              key={course.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.05, duration: 0.35 }}
              className="edu-card rounded-3xl p-6"
            >
              <h2 className="font-heading text-xl font-bold text-slate-800 truncate">
                {course.name}
              </h2>
              {course.code && (
                <p className="text-sm text-indigo-500 font-medium mt-0.5">
                  {course.code}
                </p>
              )}

              <div className="mt-4 inline-flex items-center gap-2 bg-indigo-50 border border-indigo-100 rounded-xl px-3 py-2">
                <span className="text-xs text-slate-500">Join code</span>
                <span className="font-mono text-sm font-semibold text-indigo-700 tracking-widest">
                  {course.join_code}
                </span>
                <button
                  type="button"
                  onClick={() => handleCopyJoinCode(course)}
                  className="text-xs text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1 ml-1"
                >
                  {copiedId === course.id ? (
                    <>
                      <Check className="w-3.5 h-3.5" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" /> Copy
                    </>
                  )}
                </button>
              </div>

              <p className="text-xs text-slate-400 mt-3">
                Teaching Assistant:{" "}
                <span
                  className={
                    course.ta_id
                      ? "text-emerald-600 font-medium"
                      : "text-slate-500"
                  }
                >
                  {course.ta_id ? "Assigned" : "Not assigned"}
                </span>
              </p>

              <div className="mt-4 pt-4 border-t border-slate-100">
                <Link
                  to={`/courses/${course.id}`}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:text-indigo-700"
                >
                  Open course <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}