import axios from 'axios'

// 开发期由 vite proxy 转发到 FastAPI（127.0.0.1:8000）
const http = axios.create({ baseURL: '/api', timeout: 60000 })

http.interceptors.response.use(
  (res) => res.data,
  (error) => {
    const detail = error?.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg).join('；')
          : error.message || '请求失败'
    return Promise.reject(new Error(message))
  },
)

export const api = {
  overview: () => http.get('/overview'),
  meta: () => http.get('/meta'),
  scenarios: (params) => http.get('/scenarios', { params }),
  scenario: (id) => http.get(`/scenarios/${id}`),
  createScenario: (payload) => http.post('/scenarios', payload),

  batches: (params) => http.get('/batches', { params }),
  batch: (id) => http.get(`/batches/${id}`),
  createBatch: (payload) => http.post('/batches', payload),

  runs: (params) => http.get('/runs', { params }),
  run: (id) => http.get(`/runs/${id}`),
  frames: (id, params) => http.get(`/runs/${id}/frames`, { params }),
  metrics: (id) => http.get(`/runs/${id}/metrics`),
  events: (id) => http.get(`/runs/${id}/events`),
}

export default http
