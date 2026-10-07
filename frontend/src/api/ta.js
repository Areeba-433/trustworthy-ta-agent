import api from "./axios.js";

export async function getTaForCourse(courseId) {
  const res = await api.get(`/courses/${courseId}/ta`);
  return res.data.data.ta;
}

export async function updateTaForCourse(courseId, payload) {
  const res = await api.put(`/courses/${courseId}/ta`, payload);
  return res.data.data.ta;
}