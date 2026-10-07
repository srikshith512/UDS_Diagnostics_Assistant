// Thin fetch wrapper: JSON in/out, readable errors, optional actor header for the audit log.
async function request(path, { method = 'GET', body, form, text } = {}) {
  const headers = { 'X-Actor': localStorage.getItem('actor') || 'engineer' }
  if (body) headers['Content-Type'] = 'application/json'
  let res
  try {
    res = await fetch(`/api${path}`, { method, headers, body: form || (body ? JSON.stringify(body) : undefined) })
  } catch {
    throw new Error('Cannot reach the backend. Is the API running?')
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const d = (await res.json()).detail
      detail = typeof d === 'string' ? d : d?.map((e) => e.msg).join('; ') || detail
    } catch { /* non-JSON error body */ }
    throw new Error(detail)
  }
  return text ? res.text() : res.json()
}

export const api = {
  health: () => request('/health'),
  spec: () => request('/spec'),
  ask: (question) => request('/qa', { method: 'POST', body: { question } }),
  ingest: (file) => { const f = new FormData(); f.append('file', file); return request('/spec/ingest', { method: 'POST', form: f }) },
  validate: (b) => request('/validate', { method: 'POST', body: b }),
  assist: (b) => request('/assist/request', { method: 'POST', body: b }),
  tests: () => request('/tests'),
  generate: () => request('/tests/generate', { method: 'POST' }),
  addTest: (b) => request('/tests', { method: 'POST', body: b }),
  review: (id, status, comment = '') => request(`/tests/${id}/review`, { method: 'PATCH', body: { status, comment } }),
  approveDrafts: () => request('/tests/approve-drafts', { method: 'POST' }),
  run: (fault) => request('/tests/run', { method: 'POST', body: { fault } }),
  coverage: () => request('/coverage'),
  exportScript: (fmt) => request(`/export/${fmt}`, { text: true }),
  audit: () => request('/audit'),
}
