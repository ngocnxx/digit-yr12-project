
// Configuration & constants.

// Work out where the Flask back-end is.
//
// On a normal computer both servers run on 127.0.0.1, so the back-end is
// simply 127.0.0.1:5050.
//
// In GitHub Codespaces the servers run in the cloud, not on the person's
// laptop, and every port gets its own https address that looks like
// https://<name>-5500.app.github.dev. So 127.0.0.1 would point at their own
// laptop where nothing is running. Instead we take the address of this page
// and swap the front-end port for the back-end port.
//
// On a real website (and when you open http://127.0.0.1:5050) Flask sends
// this page itself, so the back-end is the same address. An empty string
// means "ask the same address this page came from".
function backendUrl() {
  if (window.NRN_API_BASE) return window.NRN_API_BASE; // manual override
  const fromSeparateServer = location.origin.includes('5500') || location.port === '5501';
  if (!fromSeparateServer) return ''; // Flask served this page
  if (location.hostname.endsWith('.app.github.dev')) {
    return location.origin.replace('-5500.', '-5050.');
  }
  return 'http://127.0.0.1:5050';
}

export const API_BASE = backendUrl();

export const TOKEN_KEY = 'ncea_token'; //label written on the storage locker-> use label key to open the box
