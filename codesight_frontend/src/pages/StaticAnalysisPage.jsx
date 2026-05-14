import { useLocation, useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { useProjectAnalysis } from '../hooks/useProjectAnalysis';
import { formatDate } from '../utils/status';

export default function StaticAnalysisPage() {
  const { id } = useParams();
  const location = useLocation();
  const sagaId = new URLSearchParams(location.search).get('saga');
  const { project, saga, results, loading } = useProjectAnalysis(id, { sagaId });
  const run = results.analysis;
  const issues = run?.issues || [];

  if (loading) {
    return (
      <div style={{ minHeight: '70vh', display: 'grid', placeItems: 'center', color: 'var(--muted)' }}>
        <RefreshCw size={32} />
      </div>
    );
  }

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Статический анализ</div>
          <h1>{project?.name || `Проект ${id}`}</h1>
          <p className="description">
            Ruff, Bandit, mypy — замечания по последнему запуску саги (шаг «Статический анализ»).
          </p>
        </div>
        <div className="hero-side">
          <div className="meta-box">
            <strong>Статус запуска</strong>
            <span>{run?.status || '—'}</span>
          </div>
          <div className="meta-box">
            <strong>Обновлено</strong>
            <span>{formatDate(run?.updated_at)}</span>
          </div>
        </div>
      </section>

      {!run && (
        <div className="card">
          <p style={{ color: 'var(--muted)', margin: 0 }}>
            Нет данных SAST для выбранной саги. Запустите полный анализ с шагом «Статический анализ» или откройте отчёт с параметром{' '}
            <code>?saga=…</code> в адресе.
          </p>
        </div>
      )}

      {run?.error_message && (
        <div className="card" style={{ background: 'var(--error-bg)', color: 'var(--error-text)' }}>
          {run.error_message}
        </div>
      )}

      {run && (
        <section className="card">
          <div className="section-header">
            <div>
              <h2>Замечания ({issues.length})</h2>
              <p>Сортировка: по серьёзности и инструменту.</p>
            </div>
          </div>
          {issues.length === 0 ? (
            <p style={{ color: 'var(--muted)', marginTop: 12 }}>Замечаний не найдено.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Инструмент</th>
                    <th>Серьёзность</th>
                    <th>Файл</th>
                    <th>Сообщение</th>
                  </tr>
                </thead>
                <tbody>
                  {issues.map((i) => (
                    <tr key={i.id}>
                      <td><strong>{i.tool}</strong></td>
                      <td>{i.severity}</td>
                      <td>
                        <small>
                          {i.file_path}
                          {i.line != null ? `:${i.line}` : ''}
                        </small>
                      </td>
                      <td>
                        <small>
                          {i.code ? `${i.code} — ` : ''}{i.message}
                        </small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {saga && (
        <p style={{ color: 'var(--muted)', fontSize: 13 }}>
          Saga: {saga.saga_id} · {saga.status}
        </p>
      )}
    </div>
  );
}
