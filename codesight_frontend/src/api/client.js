import axios from 'axios';

// Vite exposes env vars via import.meta.env at build time.
// envPrefix in vite.config.js allows both VITE_* and REACT_APP_* keys.
const env = (key, fallback) => {
  const fromMeta = import.meta.env ? import.meta.env[key] : undefined;
  if (fromMeta) return fromMeta;
  if (typeof process !== 'undefined' && process.env && process.env[key]) {
    return process.env[key];
  }
  return fallback;
};

export const SERVICE_URLS = {
  auth: env('REACT_APP_AUTH_URL', 'http://localhost:8001'),
  loader: env('REACT_APP_LOADER_URL', 'http://localhost:8002'),
  sast: env('REACT_APP_SAST_URL', 'http://localhost:8003'),
  testing: env('REACT_APP_TESTING_URL', 'http://localhost:8004'),
  security: env('REACT_APP_SECURITY_URL', 'http://localhost:8005'),
  arch: env('REACT_APP_ARCH_URL', 'http://localhost:8006'),
  orchestrator: env('REACT_APP_ORCHESTRATOR_URL', 'http://localhost:8007'),
  dast: env('REACT_APP_DAST_URL', 'http://localhost:8008'),
};

const attachToken = (config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
};

const onUnauthorized = (error) => {
  if (error.response && error.response.status === 401) {
    const path = window.location.pathname;
    if (path !== '/login' && path !== '/register') {
      localStorage.removeItem('access_token');
    }
  }
  return Promise.reject(error);
};

const makeClient = (baseURL) => {
  const instance = axios.create({ baseURL, timeout: 30000 });
  instance.interceptors.request.use(attachToken);
  instance.interceptors.response.use((response) => response, onUnauthorized);
  return instance;
};

export const authApi = makeClient(SERVICE_URLS.auth);
export const projectApi = makeClient(SERVICE_URLS.loader);
export const sastApi = makeClient(SERVICE_URLS.sast);
export const testingApi = makeClient(SERVICE_URLS.testing);
export const securityApi = makeClient(SERVICE_URLS.security);
export const archApi = makeClient(SERVICE_URLS.arch);
export const orchestratorApi = makeClient(SERVICE_URLS.orchestrator);
export const dastApi = makeClient(SERVICE_URLS.dast);

const apiByStep = {
  analysis: sastApi,
  security: securityApi,
  arch: archApi,
  testing: testingApi,
  dast: dastApi,
};

export const runEndpointForStep = (step, runId) => {
  switch (step) {
    case 'analysis':
      return { client: sastApi, url: `/analysis/runs/${runId}` };
    case 'security':
      return { client: securityApi, url: `/security/scans/${runId}` };
    case 'arch':
      return { client: archApi, url: `/arch/runs/${runId}` };
    case 'testing':
      return { client: testingApi, url: `/testing/runs/${runId}` };
    case 'dast':
      return { client: dastApi, url: `/dast/runs/${runId}` };
    default:
      return null;
  }
};

export { apiByStep };
