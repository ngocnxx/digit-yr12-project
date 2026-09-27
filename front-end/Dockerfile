# syntax=docker/dockerfile:1
# NCEA Review Navigator — static SPA container (local only, never uploaded to S3)

# Stage 1: work out the Content-Security-Policy for the "edge" port (8080).
# Same rule Terraform uses for CloudFront: hash the one inline <script> in
# index.html (regex (?s)<script>(.*?)</script>, base64 of the SHA-256 digest).
FROM python:3.13-slim AS csp
WORKDIR /src
COPY index.html .
RUN python - <<'EOF'
import base64, hashlib, re

html = open("index.html", encoding="utf-8").read()
inline = re.findall(r"(?s)<script>(.*?)</script>", html)
if len(inline) != 1:
    raise SystemExit(f"index.html must have exactly one inline <script>, found {len(inline)}")
digest = base64.b64encode(hashlib.sha256(inline[0].encode("utf-8")).digest()).decode()
csp = (
    "default-src 'none'; "
    f"script-src 'self' 'sha256-{digest}'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
with open("/csp.conf", "w", encoding="utf-8") as f:
    f.write(f'add_header Content-Security-Policy "{csp}" always;\n')
print(f"CSP script hash: sha256-{digest}")
EOF

# Stage 2: nginx serving the SPA
FROM nginx:alpine

# nginx site config (kept out of the served web root).
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=csp /csp.conf /etc/nginx/snippets/csp.conf

# Copy only the SPA assets into the web root (no Dockerfile/config/WIP leakage).
# These three are exactly what gets uploaded to the S3 web bucket on AWS.
COPY index.html /usr/share/nginx/html/
COPY style.css /usr/share/nginx/html/
COPY js/ /usr/share/nginx/html/js/

# 80 = the page for split-origin dev (API on :5050)
# 8080 = the "edge": one origin like CloudFront (/api/* forwarded, production CSP)
EXPOSE 80 8080
