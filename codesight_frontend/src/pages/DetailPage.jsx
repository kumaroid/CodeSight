import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Loader, Play, RefreshCw, Trash2 } from 'lucide-react';
import { deleteProject, getProject } from '../api/projects';
import { createSaga, listSagasForProject } from '../api/orchestrator';
import {
  PROJECT_STATUS,
  SAGA_STATUS,
  STEP_LABEL,
  formatDate,
  sagaProgress,
} from '../utils/status';

export default function DetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [sagas, setSagas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [projectData, sagasData] = await Promise.all([
        getProject(id),
        listSagasForProject(id).catch(() => []),
      ]);
      setProject(projectData);
      setSagas(sagasData);
    } catch (e) {
      setError(e.response?.data?.detail || 'Не удалось загрузить проект');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleStartAnalysis = async () => {
    setStarting(true);
    try {
      const saga = await createSaga(id);
      navigate(`/projects/${id}/status?saga=${saga.saga_id}`);
    } catch (e) {
      setError(e.response?.data?.detail || 'Не удалось запустить анализ');
    } finally {
      setStarting(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Удалить проект и все его результаты?')) return;
    try {
      await deleteProject(id);
      navigate('/projects');
    } catch (e) {
      setError(e.response?.data?.detail || 'Не удалось удалить проект');
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: '70vh', display: 'grid', placeItems: 'center', color: 'var(--muted)' }}>
        <div style={{ textAlign: 'center' }}>
          <RefreshCw size={32} style={{ margin: '0 auto 12px' }} />
          <p>Загрузка проекта...</p>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="card" style={{ background: 'var(--error-bg)', color: 'var(--error-text)' }}>
        {error || 'Проект не найден.'}
      </div>
    );
  }

  const projectMeta = PROJECT_STATUS[project.status] || { label: project.status, cls: 'pill-neutral' };
  const lastSaga = sagas[0];

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Проект</div>
          <h1>{project.name}</h1>
          <p className="description">
            {project.repo_url ? `Источник: ${project.repo_url}` : 'Загружен из ZIP-архива.'}
          </p>
          {project.error_message && (
            <p style={{ marginTop: 8, color: 'var(--error-text)', fontSize: 13 }}>
              {project.error_message}
            </p>
          )}
        </div>
        <div className="hero-side">
          <div className="meta-box">
            <strong>Статус</strong>
            <span><span className={`pill ${projectMeta.cls}`}>{projectMeta.label}</span></span>
          </div>
          <div className="meta-box">
            <strong>Источник</strong>
            <span>{project.source_type === 'git' ? 'Git repository' : 'ZIP-архив'}</span>
          </div>
          <div className="meta-box">
            <strong>Загружен</strong>
            <span>{formatDate(project.created_at)}</span>
          </div>
        </div>
      </section>

      {error && (
        <div className="card" style={{ background: 'var(--error-bg)', color: 'var(--error-text)' }}>
          {error}
        </div>
      )}

      <section className="analysis-grid">
        <article className="analysis-card">
          <div className="analysis-icon"><Play size={20} /></div>
          <h3>Запустить анализ</h3>
          <p>Запускает Saga со всеми пятью шагами: статика, безопасность, архитектура, тесты, dynamic.</p>
          <button
            className="btn btn-primary"
            onClick={handleStartAnalysis}
            disabled={starting || project.status !== 'ready'}
          >
            {starting ? <><Loader size={14} style={{ marginRight: 6 }} />Запускаем...</> : 'Запустить анализ'}
          </button>
        </article>

        <article className="analysis-card">
          <div className="analysis-icon">◫</div>
          <h3>Итоговый отчёт</h3>
          <p>Сводные метрики качества, coverage и архитектурные риски.</p>
          <button
            className="btn btn-secondary"
            onClick={() => navigate(`/projects/${id}/report${lastSaga ? `?saga=${lastSaga.saga_id}` : ''}`)}
            disabled={!lastSaga}
          >
            Открыть отчёт
          </button>
        </article>

        <article className="analysis-card">
          <div className="analysis-icon">🔒</div>
          <h3>Security</h3>
          <p>OWASP Top 10, CWE, уязвимости зависимостей.</p>
          <button
            className="btn btn-secondary"
            onClick={() => navigate(`/projects/${id}/security${lastSaga ? `?saga=${lastSaga.saga_id}` : ''}`)}
            disabled={!lastSaga}
          >
            Открыть security
          </button>
        </article>

        <article className="analysis-card">
          <div className="analysis-icon">◎</div>
          <h3>Архитектура</h3>
          <p>Граф связности, hotspot-модули, рекомендации.</p>
          <button
            className="btn btn-secondary"
            onClick={() => navigate(`/projects/${id}/architecture${lastSaga ? `?saga=${lastSaga.saga_id}` : ''}`)}
            disabled={!lastSaga}
          >
            Открыть архитектуру
          </button>
        </article>
      </section>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>История запусков</h2>
            <p>Все Saga для этого проекта</p>
          </div>
          <button className="btn btn-danger" onClick={handleDelete}>
            <Trash2 size={14} style={{ marginRight: 6 }} />Удалить проект
          </button>
        </div>
        {sagas.length === 0 ? (
          <p style={{ color: 'var(--muted)' }}>Анализ ещё не запускался.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Saga</th>
                  <th>Статус</th>
                  <th>Прогресс</th>
                  <th>Шаги</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {sagas.map((saga) => {
                  const meta = SAGA_STATUS[saga.status] || { label: saga.status, cls: 'pill-neutral' };
                  return (
                    <tr key={saga.saga_id}>
                      <td>
                        <strong style={{ fontFamily: 'monospace', fontSize: 12 }}>
                          {saga.saga_id.slice(0, 8)}
                        </strong>
                      </td>
                      <td><span className={`pill ${meta.cls}`}>{meta.label}</span></td>
                      <td>{sagaProgress(saga)}%</td>
                      <td style={{ fontSize: 12, color: 'var(--muted)' }}>
                        {Object.entries(saga.steps_status || {})
                          .map(([step, status]) => `${STEP_LABEL[step]?.label || step}: ${status}`)
                          .join(' · ')}
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: '7px 12px' }}
                          onClick={() => navigate(`/projects/${id}/status?saga=${saga.saga_id}`)}
                        >
                          Открыть
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
