import { projectApi } from './client';

export const getProjects = () => projectApi.get('/projects/');
export const getProject = (id) => projectApi.get(`/projects/${id}`);
export const deleteProject = (id) => projectApi.delete(`/projects/${id}`);
export const uploadZip = (formData, onUploadProgress) =>
  projectApi.post('/projects/upload/zip', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
  });
export const uploadRepo = (payload) => projectApi.post('/projects/upload/repo', payload);
