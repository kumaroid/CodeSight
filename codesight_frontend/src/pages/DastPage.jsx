import { useLocation, useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { useProjectAnalysis } from '../hooks/useProjectAnalysis';
import { formatDate } from '../utils/status';

export default function DastPage() {
  const { id } = useParams();
  const location = useLocation();
  const sagaId = new URLSearchParams(location.search).get('saga');
  const { project, saga, results, loading } = useProjectAnalysis(id, { sagaId });
  const run = results.dast;
  const report = run?.valgrind_report || '';
  const preview = report.length > 12000 ? `${report.slice(0, 12000)}\n\n… [обрезано, полный текст в API /dast/runs/{id}]` : report;

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
          <div className="eyebrow">Динамический анализ (DAST)</div>
          <h1>{project?.name || `Проект ${id}`}</h1>
          <p className="description">
            Valgrind/memcheck и лёгкий Python-smoke по проекту. В rootless-контейнерах Valgrind может быть недоступен — тогда выполняется fallback без него.
          </p>
        </div>
        <div className="hero-side">
          <div className="meta-box">
            <strong>Статус</strong>
            <span>{run?.status || '—'}</span>
          </div>
          <div className="meta-box">
            <strong>Режим</strong>
            <span>{run?.command_summary || '—'}</span>
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
            Нет прогона DAST для этой саги. Убедитесь, что в запуске был шаг «Динамика» (dast).
          </p>
        </div>
      )}

      {run?.error_message && (
        <div className="card" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
          <strong>Примечание:</strong> {run.error_message}
        </div>
      )}

      {run && (
        <section className="card">
          <h2>Журнал прогона</h2>
          {preview ? (
            <pre
              style={{
                marginTop: 14,
                padding: 14,
                borderRadius: 12,
                background: 'var(--surface-2)',
                fontSize: 12,
                overflow: 'auto',
                maxHeight: '70vh',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {preview}
            </pre>
          ) : (
            <p style={{ color: 'var(--muted)', marginTop: 12 }}>Текст отчёта пуст.</p>
          )}
        </section>
      )}
      {saga && (
        <p style={{ color: 'var(--muted)', fontSize: 13 }}>Saga: {saga.saga_id}</p>
      )}
    </div>
  );
}
