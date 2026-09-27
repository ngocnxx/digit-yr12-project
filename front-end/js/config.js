
// Configuration & constants.

// Work out where the Flask back-end is.
//
// On a normal computer both servers run on 127.0.0.1, so the back-end is
// simply 127.0.0.1:5050.
//
// In GitHub Codespaces every port gets its own private https address, like
// https://<name>-5500.app.github.dev, and a private port refuses calls from
// another port's page. So there we ask the same address this page came from:
// the web container forwards /api/* to Flask (and in host mode you open the
// -5050 address, where Flask sends this page itself).
//
// On a real website (CloudFront), on the local "edge" port 8080, and when you
// open http://127.0.0.1:5050, the back-end is the same address too. An empty
// string means "ask the same address this page came from".
function backendUrl() {
  if (window.NRN_API_BASE) return window.NRN_API_BASE; // manual override
  if (location.hostname.endsWith('.app.github.dev')) return ''; // Codespaces
  // Check the port itself, so a web address that just contains "5500" is not fooled
  const fromSeparateServer = location.port === '5500' || location.port === '5501';
  if (!fromSeparateServer) return ''; // Flask or the edge served this page
  return 'http://127.0.0.1:5050';
}

export const API_BASE = backendUrl();

export const TOKEN_KEY = 'ncea_token'; //label written on the storage locker-> use label key to open the box
