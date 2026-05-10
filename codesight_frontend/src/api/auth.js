import { authApi } from './client';

export const loginRequest = (email, password) => authApi.post('/auth/login', { email, password });
export const registerRequest = (email, password) => authApi.post('/auth/register', { email, password });
export const meRequest = () => authApi.get('/auth/me');
