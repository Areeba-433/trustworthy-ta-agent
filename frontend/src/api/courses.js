import api from "./axios.js";

export async function listCourses() {
  const res = await api.get("/courses");
  return res.data.data.courses;
}

export async function getCourse(courseId) {
  const res = await api.get(`/courses/${courseId}`);
  return res.data.data.course;
}

export async function createCourse(payload) {
  const res = await api.post("/courses", payload);
  return res.data.data.course;
}

export async function joinCourseByCode(code) {
  const res = await api.post("/courses/join", { code });
  return res.data.data.course;
}

export async function listMyEnrolledCourses() {
  const res = await api.get("/courses/enrolled");
  return res.data.data.courses;
}

export async function getEnrolledCourse(courseId) {
  const res = await api.get(`/courses/enrolled/${courseId}`);
  return res.data.data.course;
}

export async function leaveCourse(courseId) {
  const res = await api.delete(`/courses/${courseId}/leave`);
  return res.data;
}

export function getErrorMessage(err) {
  const detail = err?.response?.data?.detail;
  if (detail?.error?.message) return detail.error.message;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  if (err?.response?.status === 409) return "You have already joined this class.";
  if (!err?.response) return "Cannot reach the server.";
  return "Something went wrong.";
}

export function isUnauthorized(err) {
  return err?.response?.status === 401;
}

export function isForbidden(err) {
  return err?.response?.status === 403;
}