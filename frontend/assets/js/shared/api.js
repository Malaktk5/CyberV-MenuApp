import { toast } from './utils.js';
/** fetch JSON avec cookie de session ; 401 -> page de connexion ; erreurs affichées en toast. */
export async function api(url, method = 'GET', body, { quiet = false } = {}) {
  const init = {method, credentials: 'same-origin', headers: {}};
  if (body instanceof Blob) { init.body = body; init.headers['Content-Type'] = body.type || 'application/octet-stream'; }
  else if (body !== undefined) { init.body = JSON.stringify(body); init.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(url, init);
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  if (r.status === 401 && !quiet) { location.href = '/admin/login.html'; throw new Error('Non connecté'); }
  if (!r.ok) {
    const d = data?.detail, msg = typeof d === 'string' ? d : (d?.[0]?.msg || 'Erreur ' + r.status);
    if (!quiet) toast(msg, 'err'); throw new Error(msg);
  }
  return data;
}
