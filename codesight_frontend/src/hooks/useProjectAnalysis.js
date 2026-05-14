import { useCallback, useEffect, useState } from 'react';
import { getProject } from '../api/projects';
import { getSaga, listSagasForProject } from '../api/orchestrator';
import {
  getArchRun,
  getDastRun,
  getSastRun,
  getSecurityScan,
  getTestingRun,
} from '../api/analysis';

const isTerminal = (status) =>
  status === 'completed' ||
  status === 'failed' ||
  status === 'compensated' ||
  status === 'compensating';

const STEP_TO_FETCHER = {
  analysis: getSastRun,
  security: getSecurityScan,
  arch: getArchRun,
  testing: getTestingRun,
  dast: getDastRun,
};

const safe = async (fn, ...args) => {
  try {
    return await fn(...args);
  } catch (e) {
    return null;
  }
};

export function useProjectAnalysis(projectId, options = {}) {
  const { sagaId: sagaIdProp, pollInterval = 4000 } = options;
  const [project, setProject] = useState(null);
  const [saga, setSaga] = useState(null);
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchAll = useCallback(async () => {
    try {
      const projectData = await getProject(projectId);
      setProject(projectData);
    } catch (e) {
      setError(e.response?.data?.detail || 'Не удалось загрузить проект');
      setLoading(false);
      return;
    }

    let currentSaga = null;
    if (sagaIdProp) {
      currentSaga = await safe(getSaga, sagaIdProp);
    }
    if (!currentSaga) {
      const sagas = await safe(listSagasForProject, projectId);
      if (sagas && sagas.length > 0) currentSaga = sagas[0];
    }
    setSaga(currentSaga);

    if (currentSaga && currentSaga.steps_run_ids) {
      const promises = Object.entries(currentSaga.steps_run_ids).map(async ([step, runId]) => {
        const fetcher = STEP_TO_FETCHER[step];
        if (!fetcher || !runId) return [step, null];
        const data = await safe(fetcher, runId);
        return [step, data];
      });
      const settled = await Promise.all(promises);
      const map = {};
      settled.forEach(([step, data]) => {
        if (data) map[step] = data;
      });
      setResults(map);
    } else {
      setResults({});
    }
    setLoading(false);
  }, [projectId, sagaIdProp]);

  useEffect(() => {
    if (!projectId) return undefined;
    fetchAll();
    const interval = setInterval(() => {
      if (!saga || !isTerminal(saga.status)) {
        fetchAll();
      }
    }, pollInterval);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, sagaIdProp]);

  return { project, saga, results, loading, error, refresh: fetchAll };
}
