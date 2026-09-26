# NCEA Review Navigator — static SPA container
FROM nginx:alpine

# nginx site config (kept out of the served web root).
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy only the SPA assets into the web root (no Dockerfile/config/WIP leakage).
COPY index.html /usr/share/nginx/html/
COPY style.css /usr/share/nginx/html/
COPY js/ /usr/share/nginx/html/js/

EXPOSE 80
