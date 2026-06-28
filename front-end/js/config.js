// ✅
// Configuration & constants.
//
// Split-origin setup: the API runs on a different origin to this static SPA,
// so calls use an absolute base URL. Override at runtime by setting
// `window.NRN_API_BASE` before the module scripts load (e.g. for deployment).
//
// Host port 5050 (not 5000): macOS AirPlay Receiver occupies 5000, so the API's
// published host port is 5050 (see docker-compose.yml). Keep this in sync with it.

//established 
export const API_BASE = window.NRN_API_BASE || 'http://127.0.0.1:5050'; //door number that the flask is running. || = or, can define  window.NRN_API_BASE for the actual web

// Backend selection. The SPA defaults to an in-browser MOCK backend so it runs
// standalone for prototype/mockup review — only HTML/CSS/JS, no Flask, no DB.
// It switches to the real API when a real base URL is configured (deploy injects
// window.NRN_API_BASE) or you pass ?real=1. The mock mirrors the real API
// contract, so nothing else changes. See js/api.mock.js + docs/dev-and-test.md.
//   (default)  → mock        ?real=1 → real API        ?mock=1 → force mock
const _params = new URLSearchParams(window.location.search)//look at messy text start at ? mark; URLSearchParams= built in tool to turn messy string to easy to use checklist
export const USE_MOCK = _params.has('mock')
  ? /* is teh condition to the left true*/ true // Rule 1: Is '?mock' in the URL? If yes, USE_MOCK = true.No then move below // ? or : used for assign a single value immediately 
  :  /* otherwise*/_params.has('real') // Rule 2: If not, is '?real' in the URL? If yes, USE_MOCK = false!
    ? false
    : typeof window.NRN_USE_MOCK === 'boolean' // Otherwise, did the developer explicitly set a true/false setting in the window settings (NRN_USE_MOCK)?
      ? window.NRN_USE_MOCK
      : !window.NRN_API_BASE; // no real API configured → mock

export const TOKEN_KEY = 'ncea_token'; //label written on the storage locker-> use label key to open the box

export const DEFAULT_TOPIC_EMOJI = '📚';
