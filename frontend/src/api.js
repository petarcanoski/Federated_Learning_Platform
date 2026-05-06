import axios from 'axios'

const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const AUTH_KEY = 'fedhealth_mk_token'

const client = axios.create({
  baseURL: backendUrl,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_KEY)
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem(AUTH_KEY)
    }
    return Promise.reject(error)
  },
)

export function setAuthToken(token) {
  localStorage.setItem(AUTH_KEY, token)
}

export function clearAuthToken() {
  localStorage.removeItem(AUTH_KEY)
}

export function getAuthToken() {
  return localStorage.getItem(AUTH_KEY)
}

export async function login(payload) {
  const { data } = await client.post('/auth/login', payload)
  return data
}

export async function me() {
  const { data } = await client.get('/auth/me')
  return data
}

export async function getAdminDashboard() {
  const { data } = await client.get('/admin/dashboard')
  return data
}

export async function getHospitalDashboard() {
  const { data } = await client.get('/hospital/dashboard')
  return data
}

export async function createHospitalAccount(payload) {
  const { data } = await client.post('/admin/hospitals', payload)
  return data
}

export async function createExperiment(payload) {
  const { data } = await client.post('/admin/experiments', payload)
  return data
}

export async function getExperiment(jobId) {
  const { data } = await client.get(`/experiments/${jobId}`)
  return data
}

export async function runFedAvg(jobId) {
  const { data } = await client.post(`/admin/experiments/${jobId}/fedavg`)
  return data
}

export async function broadcastModel(jobId) {
  const { data } = await client.post(`/admin/experiments/${jobId}/broadcast`)
  return data
}

export async function trainHospital(jobId) {
  const url = jobId ? `/hospital/train?job_id=${encodeURIComponent(jobId)}` : '/hospital/train'
  const { data } = await client.post(url)
  return data
}

export async function exportResults(jobId) {
  const { data } = await client.get(`/admin/experiments/${jobId}/export`)
  return data
}

export { client }

