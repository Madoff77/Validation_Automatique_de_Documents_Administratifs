import apiClient from './client'

export const documentsApi = {
  list: (params = {}) =>
    apiClient.get('/documents', { params }).then((r) => r.data),

  get: (id) =>
    apiClient.get(`/documents/${id}`).then((r) => r.data),

  upload: (supplierId, file, onProgress) => {
    const form = new FormData()
    form.append('file', file)
    form.append('supplier_id', supplierId)
    return apiClient.post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress) onProgress(Math.round((e.loaded * 100) / e.total))
      },
    }).then((r) => r.data)
  },

  reprocess: (id) =>
    apiClient.post(`/documents/${id}/reprocess`).then((r) => r.data),

  delete: (id) =>
    apiClient.delete(`/documents/${id}`).then((r) => r.data),

  getDownloadUrl: (id, zone = 'raw') =>
    `${apiClient.defaults.baseURL}/documents/${id}/download?zone=${zone}`,

  getViewUrl: (id, zone = 'raw') =>
    apiClient.get(`/documents/${id}/view-url?zone=${zone}`).then((r) => r.data),
}

export const statsApi = {
  dashboard: () =>
    apiClient.get('/stats/dashboard').then((r) => r.data),
}

export const anomaliesApi = {
  list: (params = {}) =>
    apiClient.get('/anomalies', { params }).then((r) => r.data),

  resolve: (id, resolved) =>
    apiClient.patch(`/anomalies/${id}/resolve`, { resolved }).then((r) => r.data),
}
