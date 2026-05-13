import { orchestratorApi } from './client';

export const ALL_STEPS = ['analysis', 'security', 'arch', 'testing', 'dast'];

export const createSaga = (projectId, steps = ALL_STEPS) =>
  orchestratorApi
    .post('/orchestrator/sagas', { project_id: projectId, steps })
    .then((r) => r.data);

export const getSaga = (sagaId) =>
  orchestratorApi.get(`/orchestrator/sagas/${sagaId}`).then((r) => r.data);

export const listSagasForProject = (projectId) =>
  orchestratorApi
    .get('/orchestrator/sagas', { params: { project_id: projectId } })
    .then((r) => r.data || []);
