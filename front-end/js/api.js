// Server communication — token storage + a thin fetch() wrapper.

import { API_BASE, TOKEN_KEY, USE_MOCK } from './config.js';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

const REQUEST_TIMEOUT_MS = 10000;

// Call the API. Adds the Bearer token, sends/receives JSON, times out if the
// server is unreachable/slow, and throws an Error (with .status) carrying the
// server's friendly message on failure.
//
// In front-end-only mode (config USE_MOCK) it routes to an in-browser mock with
// the same contract instead of fetching — the rest of the app is unchanged.
export async function api(method, path, body) {
  if (USE_MOCK) {
    const { mockApi } = await import('./api.mock.js');
    return mockApi(method, path, body, getToken());
  }

  const opts = { method, headers: {} };
  const tok = getToken();
  if (tok) opts.headers['Authorization'] = 'Bearer ' + tok;
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  // Abort the request if it stalls, so the UI never hangs on a dead server.
  const ac = new AbortController();
  opts.signal = ac.signal;
  const timer = setTimeout(() => ac.abort(), REQUEST_TIMEOUT_MS);

  let res;
  try {
    res = await fetch(API_BASE + path, opts);
  } catch (e) {
    const msg =
      e.name === 'AbortError'
        ? 'The server took too long to respond. Please try again.'
        : "Couldn't reach the server. Check your connection and try again.";
    const err = new Error(msg);
    err.status = 0; // network/timeout, not an HTTP status
    throw err;
  } finally {
    clearTimeout(timer);
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    /* an empty body is fine */
  }

  if (!res.ok) {
    const err = new Error((data && data.error) || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}
