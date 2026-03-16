import apiClient from './client'

export const suppliersApi = {
  list: (params = {}) =>
    apiClient.get('/suppliers', { params }).then((r) => r.data),

  get: (id) =>
    apiClient.get(`/suppliers/${id}`).then((r) => r.data),

  create: (data) =>
    apiClient.post('/suppliers', data).then((r) => r.data),

  update: (id, data) =>
    apiClient.put(`/suppliers/${id}`, data).then((r) => r.data),

  delete: (id) =>
    apiClient.delete(`/suppliers/${id}`).then((r) => r.data),

  getCompliance: (id) =>
    apiClient.get(`/suppliers/${id}/compliance`).then((r) => r.data),
}
