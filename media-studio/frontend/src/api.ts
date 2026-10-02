// 网关 API 封装（开发服务器通过 vite proxy 转发到 :8200）
const BASE = '/api/v1'

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

export interface HealthMap {
  gateway: string
  analytics: string
  dtk: string
  mpt: string
}

export interface Task {
  id: string
  kind: string
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  input?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
  created_at?: string
  updated_at?: string
}

export interface ArchiveItem {
  id: string
  kind: string
  title: string
  summary?: string
  result?: Record<string, unknown>
  source_task_id?: string
  created_at?: string
}

export interface MptTask {
  mpt_task_id: string
  state?: number // -1 失败 / 1 排队 / 2 进行中 / 3 完成
  progress?: number
  videos?: string[]
  failed_stage?: string
  error?: string
}

export interface Settings {
  llm?: { base_url?: string; model?: string; api_key_configured?: boolean }
  feishu?: { app_id?: string; app_secret_configured?: boolean }
  dtk?: { api_key_configured?: boolean }
}

export interface MaterialItem {
  name: string
  size: number
  modified_at?: string
}

export const TASK_KINDS: Record<string, string> = {
  'analyze-link': '爆款视频拆解',
  'analyze-blogger': '博主对标拆解',
  'search-keywords': '关键词找爆款',
  'generate-script': '原创文案生成',
  'rewrite': '仿写三件套',
  'generate-video': '一键成片',
  'account-review': '账号复盘诊断',
}

// 后端 SQLite 中 result / input 以 JSON 字符串存储，统一在此归一化
function normalizeTask(t: Task): Task {
  const parse = (v: unknown) => {
    if (typeof v === 'string') {
      try { return JSON.parse(v) } catch { return v }
    }
    return v
  }
  return { ...t, input: parse(t.input) as Task['input'], result: parse(t.result) as Task['result'] }
}

export const api = {
  health: () => req<HealthMap>('/health'),

  createTask: (kind: string, payload: Record<string, unknown>) =>
    req<{ task_id: string; poll: string }>(`/tasks/${kind}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getTask: async (id: string) => normalizeTask(await req<Task>(`/tasks/${id}`)),
  clearTasks: () =>
    req<{ cleared: number }>('/tasks', { method: 'DELETE' }),
  listTasks: async () => {
    const raw = await req<Task[] | { tasks?: Task[] }>('/tasks')
    return (Array.isArray(raw) ? raw : raw.tasks ?? []).map(normalizeTask)
  },

  getSettings: () => req<Settings>('/settings'),
  putSettings: (body: Record<string, unknown>) =>
    req<{ status: string }>('/settings', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  listArchive: (keyword?: string, kind?: string) => {
    const q = new URLSearchParams()
    if (keyword) q.set('keyword', keyword)
    if (kind) q.set('kind', kind)
    const s = q.toString()
    return req<{ items: ArchiveItem[]; total: number }>(`/archive${s ? `?${s}` : ''}`)
  },
  deleteArchive: (id: string) =>
    req<{ deleted: boolean }>(`/archive/${id}`, { method: 'DELETE' }),

  listBloggers: () => req<{ items: Record<string, unknown>[] }>('/bloggers'),

  listMaterials: () =>
    req<{ items: MaterialItem[]; dir: string }>('/materials'),
  uploadMaterial: (file: File, onProgress?: (pct: number) => void) =>
    new Promise<{ status: string; name: string; size: number }>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${BASE}/materials`)
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
      }
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText)
          if (xhr.status >= 200 && xhr.status < 300 && !data.error) resolve(data)
          else reject(new Error(data.error || `${xhr.status} ${xhr.statusText}`))
        } catch { reject(new Error(`${xhr.status} ${xhr.statusText}`)) }
      }
      xhr.onerror = () => reject(new Error('网络错误'))
      const fd = new FormData()
      fd.append('file', file)
      xhr.send(fd)
    }),
  deleteMaterial: (name: string) =>
    req<{ deleted: boolean }>(`/materials/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  getMptTask: (tid: string) => req<MptTask>(`/mpt/tasks/${tid}`),

  feishuSync: (body: Record<string, unknown>) =>
    req<{ status: string; result?: unknown; message?: string }>('/feishu/sync', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
