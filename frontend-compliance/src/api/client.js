import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let isRefreshing = false
let failedQueue = []

const processQueue = (error, token = null) => {
  failedQueue.forEach((p) => error ? p.reject(error) : p.resolve(token))
  failedQueue = []
}

apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => failedQueue.push({ resolve, reject }))
          .then((token) => { original.headers.Authorization = `Bearer ${token}`; return apiClient(original) })
      }
      original._retry = true
      isRefreshing = true
      const rt = localStorage.getItem('refresh_token')
      if (!rt) { localStorage.clear(); window.location.href = '/login'; return Promise.reject(error) }
      try {
        const res = await axios.post(`${API_URL}/auth/refresh`, { refresh_token: rt })
        localStorage.setItem('access_token', res.data.access_token)
        localStorage.setItem('refresh_token', res.data.refresh_token)
        processQueue(null, res.data.access_token)
        original.headers.Authorization = `Bearer ${res.data.access_token}`
        return apiClient(original)
      } catch (e) { processQueue(e); localStorage.clear(); window.location.href = '/login'; return Promise.reject(e) }
      finally { isRefreshing = false }
    }
    return Promise.reject(error)
  }
)

export default apiClient
