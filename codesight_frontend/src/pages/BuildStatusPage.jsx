import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { CheckCircle, Loader, RefreshCw, Square, XCircle } from 'lucide-react';
import { getProject } from '../api/projects';
import { cancelSaga, createSaga, getSaga, listSagasForProject } from '../api/orchestrator';
import {
  PROJECT_STATUS,
  SAGA_STATUS,
  STEP_LABEL,
  STEP_STATUS,
  STEPS_ORDER,
  sagaProgress,
} from '../utils/status';

const BACKEND_LOGS = [
  { name: 'Оркестратор (Saga)', cmd: 'podman logs -f codesight_orchestrator_service' },
  { name: 'Статический анализ (SAST)', cmd: 'podman logs -f codesight_analysis_service' },
  { name: 'Безопасность', cmd: 'podman logs -f codesight_security_service' },
  { name: 'Архитектура', cmd: 'podman logs -f codesight_arch_service' },
  { name: 'Тесты', cmd: 'podman logs -f codesight_testing_service' },
  { name: 'DAST (Valgrind)', cmd: 'podman logs -f codesight_dast_service' },
  { name: 'Загрузчик проектов', cmd: 'podman logs -f codesight_loader_service' },
];

export default function BuildStatusPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const initialSagaId = params.get('saga');

  const [project, setProject] = useState(null);
  const [saga, setSaga] = useState(null);
  const [sagaId, setSagaId] = useState(initialSagaId || null);
  const [loadingProject, setLoadingProject] = useState(true);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);

  const refreshProject = useCallback(async () => {
    try {
      const data = await getProject(id);
      setProject(data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Не удалось загрузить проект');
    } finally {
      setLoadingProject(false);
    }
  }, [id]);

  const refreshSaga = useCallback(async () => {
    if (!sagaId) {
      try {
        const sagas = await listSagasForProject(id);
        if (sagas[0]) {
          setSagaId(sagas[0].saga_id);
          setSaga(sagas[0]);
        }
      } catch {
        // ignore
      }
      return;
    }
    try {
      const data = await getSaga(sagaId);
      setSaga(data);
    } catch {
      // saga might be missing; ignore for polling
    }
  }, [id, sagaId]);

  useEffect(() => {
    refreshProject();
  }, [refreshProject]);

  useEffect(() => {
    refreshSaga();
    const interval = setInterval(refreshSaga, 3500);
    return () => clearInterval(interval);
  }, [refreshSaga]);

  const handleStart = async () => {
    setStarting(true);
    setError('');
    try {
      const data = await createSaga(id);
      setSagaId(data.saga_id);
      setSaga(data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Не удалось запустить анализ');
    } finally {
      setStarting(false);
    }
  };

  const handleStop = async () => {
    if (!sagaId || !window.confirm('Остановить анализ? Завершённые шаги будут откатаны (компенсация Saga).')) return;
    setStopping(true);
    setError('');
    try {
      const data = await cancelSaga(sagaId);
      setSaga(data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Не удалось остановить анализ');
    } finally {
      setStopping(false);
    }
  };

  const progress = useMemo(() => sagaProgress(saga), [saga]);
  const sagaMeta = saga
    ? SAGA_STATUS[saga.status] || { label: saga.status, cls: 'pill-neutral' }
    : null;

  const activityLog = Array.isArray(saga?.activity_log) ? saga.activity_log : [];
  const canStop = saga && (saga.status === 'running' || saga.status === 'pending');

  if (loadingProject) {
    return (
      <div style={{ minHeight: '70vh', display: 'grid', placeItems: 'center', color: 'var(--muted)' }}>
        <div style={{ textAlign: 'center' }}>
          <RefreshCw size={32} style={{ margin: '0 auto 12px' }} />
          <p>Загрузка проекта...</p>
        </div>
      </div>
    );
  }

  const projectMeta = project ? PROJECT_STATUS[project.status] : null;
  const stepsToShow = saga
    ? Object.keys(saga.steps_status || {})
    : STEPS_ORDER;

  return (
    <div className="container">
      <section className="hero">
        <div>
          <p className="eyebrow">Статус анализа</p>
          <h1>{project?.name || `Проект #${id || '—'}`}</h1>
          <p className="description">
            Платформа проходит шаги анализа через Saga-оркестратор. Ниже — журнал событий оркестратора; полные логи сервисов смотрите в терминале (раздел ниже).
          </p>
          {project?.repo_url && (
            <p style={{ marginTop: 8, color: 'var(--muted)', fontSize: 13 }}>{project.repo_url}</p>
          )}
        </div>
        <div className="hero-side">
          <div className="meta-box">
            <strong>Проект</strong>
            <span>
              {projectMeta ? (
                <span className={`pill ${projectMeta.cls}`}>{projectMeta.label}</span>
              ) : (
                '—'
              )}
            </span>
          </div>
          <div className="meta-box">
            <strong>Saga</strong>
            <span>
              {sagaMeta ? (
                <span className={`pill ${sagaMeta.cls}`}>{sagaMeta.label}</span>
              ) : (
                <span className="pill pill-neutral">Не запущена</span>
              )}
            </span>
          </div>
          <div className="meta-box">
            <strong>Прогресс</strong>
            <span style={{ fontSize: 22, fontWeight: 700 }}>{progress}%</span>
          </div>
        </div>
      </section>

      {error && (
        <div className="card" style={{ borderColor: 'rgba(161,53,68,0.2)', background: 'var(--error-bg)', color: 'var(--error-text)' }}>
          {error}
        </div>
      )}

      <div className="card">
        <div className="section-header">
          <div>
            <h2>Прогресс выполнения</h2>
            <p>Шаги распределённого анализа</p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {saga?.status === 'running' && (
              <span className="pill pill-running"><Loader size={12} style={{ marginRight: 4 }} />Выполняется</span>
            )}
            {saga?.status === 'completed' && (
              <span className="pill pill-success"><CheckCircle size={12} style={{ marginRight: 4 }} />Готово</span>
            )}
            {saga?.status === 'failed' && (
              <span className="pill pill-error"><XCircle size={12} style={{ marginRight: 4 }} />Ошибка</span>
            )}
            {(saga?.status === 'compensating' || saga?.status === 'compensated') && (
              <span className="pill pill-warning">Остановка / откат</span>
            )}
            {canStop && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleStop}
                disabled={stopping}
                title="Отменить сагу и отправить компенсации"
              >
                <Square size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                {stopping ? 'Останавливаем…' : 'Остановить анализ'}
              </button>
            )}
            {!saga && (
              <button
                className="btn btn-primary"
                onClick={handleStart}
                disabled={starting || project?.status !== 'ready'}
              >
                {starting ? 'Запускаем...' : 'Запустить анализ'}
              </button>
            )}
          </div>
        </div>

        <div className="bar-wrap">
          <div className="bar-top">
            <span>Общий прогресс</span>
            <span>{progress}%</span>
          </div>
          <div className="bar"><span className="bar-fill" style={{ width: `${progress}%` }} /></div>
        </div>

        <div className="stages">
          {stepsToShow.map((step) => {
            const stepStatus = (saga?.steps_status || {})[step] || 'pending';
            const meta = STEP_STATUS[stepStatus] || STEP_STATUS.pending;
            const label = STEP_LABEL[step] || { label: step, desc: '' };
            return (
              <div key={step} className={`stage ${meta.stageCls}`}>
                <strong>{label.label}</strong>
                <span>{label.desc}</span>
                <span style={{ display: 'block', marginTop: 8 }}>
                  <span className={`pill ${meta.cls}`}>{meta.label}</span>
                </span>
              </div>
            );
          })}
        </div>

        {saga?.error_message && (
          <div style={{
            marginTop: 16, padding: '12px 14px', borderRadius: 12,
            background: 'var(--error-bg)', color: 'var(--error-text)', fontSize: 13,
          }}>
            {saga.error_message}
          </div>
        )}
      </div>

      {sagaId && (
        <div className="card">
          <div className="section-header">
            <div>
              <h2>Журнал анализа (оркестратор)</h2>
              <p>События Saga: команды в Kafka, результаты шагов. Обновляется при опросе API.</p>
            </div>
          </div>
          {activityLog.length === 0 ? (
            <p style={{ color: 'var(--muted)', marginTop: 8 }}>Пока нет записей — запустите анализ или подождите несколько секунд.</p>
          ) : (
            <pre
              style={{
                marginTop: 12,
                padding: 14,
                borderRadius: 12,
                background: 'var(--surface-2)',
                fontSize: 12,
                maxHeight: 320,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
              }}
            >
              {activityLog.map((e, idx) => {
                const ts = e.ts || '';
                const lvl = e.level || 'info';
                const step = e.step ? `[${e.step}] ` : '';
                const msg = e.message || '';
                return `${idx + 1}. ${ts} ${lvl} ${step}${msg}\n`;
              })}
            </pre>
          )}
        </div>
      )}

      <div className="card">
        <div className="section-header">
          <div>
            <h2>Логи бэкенда (терминал)</h2>
            <p>
              Веб-интерфейс показывает только сводку оркестратора. Полные логи микросервисов — через Docker/Podman на машине, где запущен стек.
              Замените <code>podman</code> на <code>docker</code>, если используете Docker Engine.
            </p>
          </div>
        </div>
        <ul style={{ margin: '12px 0 0', paddingLeft: 18, color: 'var(--muted)', fontSize: 14 }}>
          {BACKEND_LOGS.map((row) => (
            <li key={row.name} style={{ marginBottom: 10 }}>
              <strong style={{ color: 'var(--text)' }}>{row.name}</strong>
              <pre
                style={{
                  marginTop: 6,
                  padding: 10,
                  borderRadius: 8,
                  background: 'var(--surface-2)',
                  fontSize: 12,
                  overflowX: 'auto',
                }}
              >
                {row.cmd}
              </pre>
            </li>
          ))}
        </ul>
      </div>

      {saga?.status === 'completed' && (
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => navigate(`/projects/${id}/report?saga=${saga.saga_id}`)}>
            Смотреть отчёт →
          </button>
          <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}`)}>
            К проекту
          </button>
        </div>
      )}
    </div>
  );
}
