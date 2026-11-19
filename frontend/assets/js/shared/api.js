import { toast } from './utils.js';

/**
 * Send a JSON or raw Blob request using the session cookie.
 * A 401 redirects staff users to the login page unless quiet mode is used.
 */
export async function api(url, method = 'GET', body, { quiet = false } = {}) {
    const init = {
        method,
        credentials: 'same-origin',
        headers: {},
    };

    if (body instanceof Blob) {
        init.body = body;
        init.headers['Content-Type'] = body.type || 'application/octet-stream';
    } else if (body !== undefined) {
        init.body = JSON.stringify(body);
        init.headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, init);
    const data = response.status === 204
        ? null
        : await response.json().catch(() => null);

    if (response.status === 401 && !quiet) {
        location.href = '/admin/login.html';
        throw new Error('Non connecté');
    }

    if (!response.ok) {
        const detail = data?.detail;
        const message = typeof detail === 'string'
            ? detail
            : detail?.[0]?.msg || `Erreur ${response.status}`;

        if (!quiet) {
            toast(message, 'err');
        }

        throw new Error(message);
    }

    return data;
}
