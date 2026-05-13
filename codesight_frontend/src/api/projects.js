import { projectApi } from './client';

export const getProjects = async () => {
  const response = await projectApi.get('/projects/');
  const items = Array.isArray(response.data) ? response.data : response.data?.items || [];
  return items;
};

export const getProject = (id) => projectApi.get(`/projects/${id}`).then((r) => r.data);

export const deleteProject = (id) => projectApi.delete(`/projects/${id}`);

export const uploadZip = (formData, onUploadProgress) =>
  projectApi
    .post('/projects/upload/zip', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
      timeout: 120000,
    })
    .then((r) => r.data);

export const uploadRepo = (payload) =>
  projectApi.post('/projects/upload/repo', payload, { timeout: 180000 }).then((r) => r.data);
