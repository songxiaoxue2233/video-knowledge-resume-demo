import { request } from '@/utils/request.js'

function toQuery(params = {}) {
  return Object.keys(params)
    .filter((key) => params[key] !== undefined && params[key] !== null && params[key] !== '')
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join('&')
}

export const api = {
  health: () => request('/api/health'),
  login: (data) => request('/api/auth/login', { method: 'POST', data }),
  register: (data) => request('/api/auth/register', { method: 'POST', data }),
  me: () => request('/api/me'),
  integrationStatus: () => request('/api/integrations/status'),
  integrationAuthUrl: (provider) => request(`/api/integrations/${provider}/auth-url`),
  disconnectIntegration: (provider) => request(`/api/integrations/${provider}`, { method: 'DELETE' }),
  parserStatus: () => request('/api/system/parser-status'),
  dashboard: () => request('/api/dashboard'),
  listNotes: (params = {}) => request(`/api/notes?${toQuery(params)}`),
  getNote: (id) => request(`/api/notes/${id}`),
  createImportTasks: (links) => request('/api/import-tasks', { method: 'POST', data: { links } }),
  listImportTasks: (params = {}) => request(`/api/import-tasks?${toQuery(params)}`),
  getImportTask: (id) => request(`/api/import-tasks/${id}`),
  updateNote: (id, data) => request(`/api/notes/${id}`, { method: 'PATCH', data }),
  deleteNote: (id) => request(`/api/notes/${id}`, { method: 'DELETE' }),
  archiveNote: (id) => request(`/api/notes/${id}/archive`, { method: 'POST' }),
  addAnnotation: (id, text) => request(`/api/notes/${id}/annotations`, { method: 'POST', data: { text } }),
  folders: () => request('/api/folders'),
  createFolder: (name) => request('/api/folders', { method: 'POST', data: { name } }),
  updateFolder: (id, name) => request(`/api/folders/${id}`, { method: 'PATCH', data: { name } }),
  deleteFolder: (id) => request(`/api/folders/${id}`, { method: 'DELETE' }),
  tags: () => request('/api/tags'),
  createTag: (name) => request('/api/tags', { method: 'POST', data: { name } }),
  updateTag: (id, name) => request(`/api/tags/${id}`, { method: 'PATCH', data: { name } }),
  deleteTag: (id) => request(`/api/tags/${id}`, { method: 'DELETE' }),
  syncFeishu: (ids) => request('/api/sync/feishu', { method: 'POST', data: { ids } }),
  exportWord: (ids) => request('/api/export/word', { method: 'POST', data: { ids } }),
  exportMarkdown: (ids) => request('/api/export/markdown', { method: 'POST', data: { ids } }),
  exportRecords: () => request('/api/export-records'),
  paymentConfig: () => request('/api/payments/config'),
  createPaymentOrder: (data) => request('/api/payments/orders', { method: 'POST', data }),
  paymentOrder: (outTradeNo) => request(`/api/payments/orders/${outTradeNo}`),
  paymentOrders: () => request('/api/payments/orders')
}
