import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Bot, Pencil, X, Check, ArrowRight } from "lucide-react";
import toast from "react-hot-toast";
import { getTaForCourse, updateTaForCourse } from "../api/ta.js";
import { getErrorMessage } from "../api/courses.js";

const STATUS_LABELS = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  INACTIVE: "Inactive",
};

const STATUS_STYLES = {
  DRAFT: "bg-slate-100 text-slate-600 border-slate-200",
  ACTIVE: "bg-emerald-50 text-emerald-600 border-emerald-200",
  INACTIVE: "bg-red-50 text-red-600 border-red-200",
};

function disabledHint(status) {
  if (status === "INACTIVE") {
    return "This assistant has been turned off by your teacher.";
  }
  if (status === "DRAFT") {
    return "This assistant is a draft. Your teacher is still setting it up.";
  }
  return "";
}

/**
 * Props:
 *   courseId   — UUID of the course
 *   isTeacher  — boolean
 *   initialTa  — TA object passed in by the parent (used for students,
 *                so they never hit the teacher-only /ta endpoint)
 */
export default function TaPanel({ courseId, isTeacher, initialTa = null }) {
  const [ta, setTa] = useState(initialTa);
  const [loading, setLoading] = useState(isTeacher && !initialTa);
  const [error, setError] = useState("");

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(initialTa?.name || "");
  const [status, setStatus] = useState(initialTa?.status || "DRAFT");
  const [saving, setSaving] = useState(false);

  // Only teachers fetch. Students use initialTa from the course response.
  useEffect(() => {
    if (!isTeacher) return;
    let cancelled = false;
    setLoading(true);
    getTaForCourse(courseId)
      .then((data) => {
        if (!cancelled) {
          setTa(data);
          setName(data.name);
          setStatus(data.status);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, isTeacher]);

  async function handleSave(e) {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Name is required");
      return;
    }
    setSaving(true);
    try {
      const updated = await updateTaForCourse(courseId, {
        name: name.trim(),
        status,
      });
      setTa(updated);
      setEditing(false);
      toast.success("Teaching assistant updated");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    if (ta) {
      setName(ta.name);
      setStatus(ta.status);
    }
    setEditing(false);
  }

  return (
    <div className="mt-6">
      <h2 className="font-heading text-lg font-semibold text-slate-700 flex items-center gap-2 mb-3">
        <Bot className="w-5 h-5 text-indigo-500" />
        Teaching Assistant
      </h2>

      {loading && (
        <div className="text-sm text-slate-500">Loading TA...</div>
      )}

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-2">
          {error}
        </div>
      )}

      {!loading && !error && !ta && (
        <div className="text-sm text-slate-500 bg-slate-50 border border-slate-100 rounded-2xl p-5">
          No teaching assistant yet.
        </div>
      )}

      {ta && !editing && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-slate-50 border border-slate-100 rounded-2xl p-5"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="font-heading text-base font-bold text-slate-800 truncate">
                {ta.name}
              </p>
              <span
                className={`inline-block mt-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${
                  STATUS_STYLES[ta.status] || STATUS_STYLES.DRAFT
                }`}
              >
                {STATUS_LABELS[ta.status] || ta.status}
              </span>
            </div>
            {isTeacher && (
              <button
                onClick={() => setEditing(true)}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:text-indigo-700"
              >
                <Pencil className="w-3.5 h-3.5" /> Edit
              </button>
            )}
          </div>

          {/* Open Teaching Assistant — enabled when ACTIVE, or always for teachers */}
          <div className="mt-4 pt-4 border-t border-slate-100">
            {ta.status === "ACTIVE" || isTeacher ? (
              <Link
                to={`/courses/${courseId}/ta`}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-blue-600 text-white text-sm font-medium px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-500/25 hover:opacity-95 transition-opacity"
              >
                <Bot className="w-4 h-4" />
                Open Teaching Assistant
                <ArrowRight className="w-4 h-4" />
              </Link>
            ) : (
              <>
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center gap-2 bg-slate-200 text-slate-500 text-sm font-medium px-5 py-2.5 rounded-xl cursor-not-allowed"
                >
                  <Bot className="w-4 h-4" />
                  Open Teaching Assistant
                  <ArrowRight className="w-4 h-4" />
                </button>
                <p className="text-xs text-slate-500 mt-2">
                  {disabledHint(ta.status)}
                </p>
              </>
            )}
          </div>
        </motion.div>
      )}

      {ta && editing && isTeacher && (
        <form
          onSubmit={handleSave}
          className="bg-slate-50 border border-slate-200 rounded-2xl p-5 grid gap-3"
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">Edit TA</span>
            <button
              type="button"
              onClick={handleCancel}
              className="text-slate-400 hover:text-slate-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div>
            <label className="text-xs text-slate-500 block mb-1">Name</label>
            <input
              type="text"
              value={name}
              maxLength={150}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400"
            />
          </div>

          <div>
            <label className="text-xs text-slate-500 block mb-1">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400"
            >
              <option value="DRAFT">Draft</option>
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-blue-600 text-white text-sm font-medium px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-500/25 disabled:opacity-60"
            >
              <Check className="w-4 h-4" />
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              className="text-sm text-slate-500 hover:text-slate-700 px-3 py-2.5"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}