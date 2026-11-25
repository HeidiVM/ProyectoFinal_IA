export async function api(path, options = {}) {
  const response = await fetch(path, options)
  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json')
    ? await response.json()
    : await response.text()
  if (!response.ok) {
    throw new Error(data?.detail || data || `Error ${response.status}`)
  }
  return data
}

export function getJson(path) {
  return api(path)
}

export function postJson(path, body) {
  return api(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
}

export function putJson(path, body) {
  return api(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
}

export function postForm(path, body) {
  return api(path, { method: 'POST', body })
}

export function cameraPreviewUrl(key) {
  return `/api/camera/snapshot?t=${key}`
}
