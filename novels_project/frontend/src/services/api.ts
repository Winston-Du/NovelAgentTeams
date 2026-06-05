import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败';
    console.error(`[API Error] ${error.config?.url}: ${message}`);
    return Promise.reject(error);
  },
);

export default api;

// ============================================================
// 工作空间 API
// ============================================================
export const workspaceApi = {
  list: () => api.get('/workspaces/'),
  create: (data: { name: string; base_path?: string }) => api.post('/workspaces/', data),
  rename: (name: string, newName: string) => api.put(`/workspaces/${name}`, { new_name: newName }),
  delete: (name: string) => api.delete(`/workspaces/${name}`),
  switch: (name: string) => api.post(`/workspaces/${name}/switch`),
  status: (name: string) => api.get(`/workspaces/${name}/status`),
};

// ============================================================
// 内容管理 API
// ============================================================
export const contentApi = {
  // 人物卡
  getCharacters: () => api.get('/content/characters'),
  getCharacter: (name: string) => api.get(`/content/characters/${encodeURIComponent(name)}`),
  createCharacter: (data: any) => api.post('/content/characters', data),
  updateCharacter: (name: string, data: any) => api.put(`/content/characters/${encodeURIComponent(name)}`, data),
  deleteCharacter: (name: string) => api.delete(`/content/characters/${encodeURIComponent(name)}`),

  // 章节
  getChapters: () => api.get('/content/chapters'),
  getChapter: (id: string) => api.get(`/content/chapters/${id}`),
  getChapterSummary: (id: string) => api.get(`/content/chapters/${id}/summary`),

  // 暗线
  getPlotLines: () => api.get('/content/plotlines'),
  createPlotLine: (data: any) => api.post('/content/plotlines', data),
  updatePlotLine: (id: string, data: any) => api.put(`/content/plotlines/${id}`, data),
  deletePlotLine: (id: string) => api.delete(`/content/plotlines/${id}`),

  // 搜索
  search: (q: string) => api.get('/content/search', { params: { q } }),

  // AI 优化
  optimizeCharacter: (data: { field: string; current_value: string; character_name: string; context?: Record<string, unknown> }) =>
    api.post('/content/characters/optimize', data),

  // 批注
  annotate: (data: any) => api.post('/content/annotate', data),
};

// ============================================================
// Agent 配置 API
// ============================================================
export const agentApi = {
  list: () => api.get('/agents/'),
  get: (name: string) => api.get(`/agents/${name}`),
  update: (name: string, data: any) => api.put(`/agents/${name}`, data),
  toggle: (name: string, enabled: boolean) => api.put(`/agents/${name}/toggle`, { enabled }),
  status: (name: string) => api.get(`/agents/${name}/status`),
  getModels: () => api.get('/agents/models'),
};

// ============================================================
// 系统设置 API
// ============================================================
export const settingsApi = {
  get: () => api.get('/settings/'),
  update: (data: any) => api.put('/settings/', data),
  backups: () => api.get('/settings/backups'),
  createBackup: () => api.post('/settings/backup'),
  restore: (name: string) => api.post('/settings/restore', null, { params: { backup_name: name } }),
  getModels: () => api.get('/settings/models'),
  saveModelProvider: (name: string, data: any) => api.post('/settings/models', { provider_key: name, ...data }),
  updateModelProvider: (name: string, data: any) => api.put(`/settings/models/${name}`, data),
  deleteModelProvider: (name: string) => api.delete(`/settings/models/${name}`),
  testProvider: (data: { base_url: string; api_key: string; model_id?: string; protocol?: string }) =>
    api.post('/settings/models/test', data),
};

// ============================================================
// 记忆管理 API
// ============================================================
export const memoryApi = {
  getEntities: (params?: any) => api.get('/memory/entities', { params }),
  getEntity: (id: string) => api.get(`/memory/entities/${encodeURIComponent(id)}`),
  updateEntity: (id: string, data: any) => api.put(`/memory/entities/${encodeURIComponent(id)}`, data),
  deleteEntity: (id: string) => api.delete(`/memory/entities/${encodeURIComponent(id)}`),
  getRelations: (params?: any) => api.get('/memory/relations', { params }),
  createRelation: (data: any) => api.post('/memory/relations', data),
  deleteRelation: (source: string, target: string) => api.delete('/memory/relations', { params: { source, target } }),
  getNetwork: (name: string, depth = 2) => api.get(`/memory/network/${encodeURIComponent(name)}`, { params: { depth } }),
  getForeshadowing: () => api.get('/memory/foreshadow'),
  getStats: () => api.get('/memory/stats'),
  search: (q: string) => api.get('/memory/search', { params: { q } }),
  sync: () => api.post('/memory/sync'),
  init: () => api.post('/memory/init'),
};