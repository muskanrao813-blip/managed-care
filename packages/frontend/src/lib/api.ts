import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

export default api;

// Patients
export const patientsApi = {
  create: (data: unknown) => api.post('/patients', data),
  list: () => api.get('/patients'),
  get: (id: string) => api.get(`/patients/${id}`),
  update: (id: string, data: unknown) => api.patch(`/patients/${id}`, data),
  submitLabReport: (id: string, labValues: Record<string, number>, source?: string) =>
    api.post(`/patients/${id}/lab-report`, { labValues, source }),
  getLabReports: (id: string) => api.get(`/patients/${id}/lab-reports`),
  submitHra: (id: string, hraAnswers: unknown) => api.post(`/patients/${id}/hra`, { hraAnswers }),
  getHraHistory: (id: string) => api.get(`/patients/${id}/hra`),
  getPlan: (id: string) => api.get(`/patients/${id}/plan`),
  getPlanDay: (id: string, day: number) => api.get(`/patients/${id}/plan/${day}`),
  rebuildPlan: (id: string) => api.post(`/patients/${id}/plan/rebuild`),
};

// Activities
export const activitiesApi = {
  complete: (id: string, completionData?: unknown) =>
    api.post(`/activities/${id}/complete`, { completionData }),
  attempt: (id: string, completionData?: unknown) =>
    api.post(`/activities/${id}/attempt`, { completionData }),
  getToday: (patientId: string) => api.get(`/activities/patient/${patientId}/today`),
};

// Appointments
export const appointmentsApi = {
  list: (patientId: string) => api.get(`/appointments/patient/${patientId}`),
  create: (data: unknown) => api.post('/appointments', data),
  update: (id: string, data: unknown) => api.patch(`/appointments/${id}`, data),
  submitPrescription: (id: string, notes: string) =>
    api.post(`/appointments/${id}/submit-prescription`, { notes }),
  receiveLabResults: (id: string, labValues?: unknown) =>
    api.post(`/appointments/${id}/receive-lab-results`, { labValues }),
  generateDietPlan: (id: string, planNotes?: string) =>
    api.post(`/appointments/${id}/generate-diet-plan`, { planNotes }),
};

// Nudges
export const nudgesApi = {
  send: (data: unknown) => api.post('/nudges/send', data),
  getHistory: (patientId: string) => api.get(`/nudges/patient/${patientId}`),
  respond: (id: string, response: string) => api.post(`/nudges/${id}/respond`, { response }),
  processEscalations: () => api.post('/nudges/process-escalations'),
};

// Outcomes
export const outcomesApi = {
  get: (patientId: string) => api.get(`/outcomes/patient/${patientId}`),
  recalculate: (patientId: string) => api.post(`/outcomes/recalculate/${patientId}`),
};

// SFDC
export const sfdcApi = {
  getTasks: (params?: { status?: string; priority?: string }) =>
    api.get('/sfdc/tasks', { params }),
  getPatientTasks: (patientId: string) => api.get(`/sfdc/tasks/patient/${patientId}`),
  updateTask: (id: string, data: { status?: string; outcome?: string; agentNotes?: string }) =>
    api.patch(`/sfdc/tasks/${id}`, data),
};

// Wellness sessions
export const wellnessApi = {
  get: (patientId: string, activityId: string) =>
    api.get(`/wellness-sessions/patient/${patientId}/${activityId}`),
  create: (data: unknown) => api.post('/wellness-sessions', data),
  update: (id: string, data: unknown) => api.patch(`/wellness-sessions/${id}`, data),
};

// Logs
export const logsApi = {
  logSteps: (data: unknown) => api.post('/step-logs', data),
  getTodaySteps: (patientId: string) => api.get(`/step-logs/patient/${patientId}/today`),
  logMeal: (data: unknown) => api.post('/meal-logs', data),
  getTodayMeals: (patientId: string) => api.get(`/meal-logs/patient/${patientId}/today`),
  logMood: (data: unknown) => api.post('/mood-logs', data),
  getRecentMoods: (patientId: string) => api.get(`/mood-logs/patient/${patientId}/recent`),
};
