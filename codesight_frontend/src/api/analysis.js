import { archApi, dastApi, sastApi, securityApi, testingApi } from './client';

export const getSastRun = (runId) =>
  sastApi.get(`/analysis/runs/${runId}`).then((r) => r.data);

export const getSastRunsForProject = (projectId) =>
  sastApi.get(`/analysis/projects/${projectId}/runs`).then((r) => r.data?.items || []);

export const getSecurityScan = (scanId) =>
  securityApi.get(`/security/scans/${scanId}`).then((r) => r.data);

export const getSecurityScansForProject = (projectId) =>
  securityApi
    .get(`/security/projects/${projectId}/scans`)
    .then((r) => r.data?.items || []);

export const getArchRun = (runId) =>
  archApi.get(`/arch/runs/${runId}`).then((r) => r.data);

export const getArchRunsForProject = (projectId) =>
  archApi.get(`/arch/projects/${projectId}/runs`).then((r) => r.data?.items || []);

export const getTestingRun = (runId) =>
  testingApi.get(`/testing/runs/${runId}`).then((r) => r.data);

export const getDastRun = (runId) =>
  dastApi.get(`/dast/runs/${runId}`).then((r) => r.data);

export const getTestingRunsForProject = (projectId) =>
  testingApi.get(`/testing/projects/${projectId}/runs`).then((r) => r.data?.items || []);

export const getCompletenessReport = (projectId) =>
  testingApi.get(`/testing/projects/${projectId}/completeness`).then((r) => r.data);
