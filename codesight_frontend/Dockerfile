FROM docker.io/library/node:20-alpine AS builder
WORKDIR /app

# Reliability tweaks for npm in rootless container builds.
ENV npm_config_audit=false \
    npm_config_fund=false \
    npm_config_progress=true \
    npm_config_maxsockets=3 \
    npm_config_fetch_retries=5 \
    npm_config_fetch_retry_mintimeout=20000 \
    npm_config_fetch_retry_maxtimeout=120000

COPY package.json ./
RUN npm install

COPY index.html ./
COPY src ./src
COPY vite.config.js ./

ARG REACT_APP_AUTH_URL=http://localhost:8001
ARG REACT_APP_LOADER_URL=http://localhost:8002
ARG REACT_APP_SAST_URL=http://localhost:8003
ARG REACT_APP_TESTING_URL=http://localhost:8004
ARG REACT_APP_SECURITY_URL=http://localhost:8005
ARG REACT_APP_ARCH_URL=http://localhost:8006
ARG REACT_APP_ORCHESTRATOR_URL=http://localhost:8007
ARG REACT_APP_DAST_URL=http://localhost:8008

ENV REACT_APP_AUTH_URL=$REACT_APP_AUTH_URL \
    REACT_APP_LOADER_URL=$REACT_APP_LOADER_URL \
    REACT_APP_SAST_URL=$REACT_APP_SAST_URL \
    REACT_APP_TESTING_URL=$REACT_APP_TESTING_URL \
    REACT_APP_SECURITY_URL=$REACT_APP_SECURITY_URL \
    REACT_APP_ARCH_URL=$REACT_APP_ARCH_URL \
    REACT_APP_ORCHESTRATOR_URL=$REACT_APP_ORCHESTRATOR_URL \
    REACT_APP_DAST_URL=$REACT_APP_DAST_URL

RUN npm run build

FROM docker.io/library/nginx:1.27-alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
