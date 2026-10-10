FROM nginx:1.27-alpine
ARG BUILD_NUMBER=dev
COPY src /usr/share/nginx/html
# Overwrites the local placeholder so the footer shows the real build number
RUN echo "window.BUILD_NUMBER='${BUILD_NUMBER}';" > /usr/share/nginx/html/js/build.js
HEALTHCHECK --interval=15s --timeout=3s CMD wget -qO- http://localhost/ || exit 1