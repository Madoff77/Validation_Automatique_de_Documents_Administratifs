import apiClient from './client'

export const authApi = {
  login: (username, password) =>
    apiClient.post('/auth/login', { username, password }).then((r) => r.data),

  logout: (refreshToken) =>
    apiClient.post('/auth/logout', { refresh_token: refreshToken }).then((r) => r.data),

  refresh: (refreshToken) =>
    apiClient.post('/auth/refresh', { refresh_token: refreshToken }).then((r) => r.data),

  me: () => apiClient.get('/auth/me').then((r) => r.data),
}
