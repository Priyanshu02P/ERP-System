const API = '/api/v1';

export async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch (e) {
      // response wasn't JSON — keep default detail
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}
