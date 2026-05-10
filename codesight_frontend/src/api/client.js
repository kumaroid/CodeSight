import axios from 'axios';

const AUTH_BASE = process.env.REACT_APP_AUTH_URL || 'http://localhost:8001';
const PROJECT_BASE = process.env.REACT_APP_PROJECT_URL || 'http://localhost:8002';

export const authApi = axios.create({ baseURL: AUTH_BASE });
export const projectApi = axios.create({ baseURL: PROJECT_BASE });

const attachToken = (config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
};

authApi.interceptors.request.use(attachToken);
projectApi.interceptors.request.use(attachToken);
