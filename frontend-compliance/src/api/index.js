import apiClient from './client'

export const authApi = {
  login: (username, password) => apiClient.post('/auth/login', { username, password }).then(r => r.data),
  logout: (rt) => apiClient.post('/auth/logout', { refresh_token: rt }).then(r => r.data),
  me: () => apiClient.get('/auth/me').then(r => r.data),
}

export const suppliersApi = {
  list: (params = {}) => apiClient.get('/suppliers', { params }).then(r => r.data),
  get: (id) => apiClient.get(`/suppliers/${id}`).then(r => r.data),
  getCompliance: (id) => apiClient.get(`/suppliers/${id}/compliance`).then(r => r.data),
}

export const anomaliesApi = {
  list: (params = {}) => apiClient.get('/anomalies', { params }).then(r => r.data),
  resolve: (id, resolved) => apiClient.patch(`/anomalies/${id}/resolve`, { resolved }).then(r => r.data),
  expiringSoon: (days = 30) => apiClient.get('/anomalies/expiring-soon', { params: { days } }).then(r => r.data),
}

export const statsApi = {
  dashboard: () => apiClient.get('/stats/dashboard').then(r => r.data),
}

export const documentsApi = {
  list: (params = {}) => apiClient.get('/documents', { params }).then(r => r.data),
  get: (id) => apiClient.get(`/documents/${id}`).then(r => r.data),
}
