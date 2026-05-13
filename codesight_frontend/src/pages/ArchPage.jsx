import { useMemo } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { useProjectAnalysis } from '../hooks/useProjectAnalysis';

const SEVERITY_PILL = {
  critical: 'pill-error',
  warning: 'pill-warning',
  info: 'pill-primary',
};

const couplingLabel = (score) => {
  if (score >= 0.7) return { label: 'Risk', cls: 'pill-error' };
  if (score >= 0.4) return { label: 'Review', cls: 'pill-warning' };
  return { label: 'Stable', cls: 'pill-success' };
};

export default function ArchPage() {
  const { id } = useParams();
  const location = useLocation();
  const sagaId = new URLSearchParams(location.search).get('saga');
  const { project, results, loading } = useProjectAnalysis(id, { sagaId });
  const run = results.arch;

  const metrics = run?.metrics || [];
  const recommendations = run?.recommendations || [];
  const summary = run?.summary || null;

  const hotspots = useMemo(
    () => [...metrics].sort((a, b) => b.coupling_score - a.coupling_score).slice(0, 6),
    [metrics],
  );

  if (loading) {
    return (
      <div style={{ minHeight: '70vh', display: 'grid', placeItems: 'center', color: 'var(--muted)' }}>
        <div style={{ textAlign: 'center' }}>
          <RefreshCw size={32} style={{ margin: '0 auto 12px' }} />
          <p>Загружаем архитектурный отчёт...</p>
        </div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="container">
        <section className="hero">
          <div>
            <div className="eyebrow">Архитектурный анализ</div>
            <h1>{project?.name || `Проект ${id}`}</h1>
            <p className="description">
              Архитектурный анализ требует PlantUML-диаграммы (`*.puml`) внутри проекта. Добавьте её в репозиторий и повторите анализ.
            </p>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Архитектурный анализ</div>
          <h1>{project?.name || `Проект ${id}`}</h1>
          <p className="description">
            Метрики связности (Coupling) и когезии (Cohesion) по PlantUML-диаграмме.
          </p>
        </div>
        <div className="hero-side">
          <div className="meta-box">
            <strong>Средний coupling</strong>
            <span>{typeof summary?.avg_coupling === 'number' ? summary.avg_coupling.toFixed(2) : '—'}</span>
          </div>
          <div className="meta-box">
            <strong>Health score</strong>
            <span>{summary?.architecture_health_score ?? '—'}</span>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Компонентные метрики</h2>
            <p>Coupling, Cohesion и Instability для каждого модуля.</p>
          </div>
          <span className="pill pill-primary">{metrics.length} компонентов</span>
        </div>
        {metrics.length === 0 ? (
          <p style={{ color: 'var(--muted)', marginTop: 12 }}>В PlantUML-файле не найдено компонентов.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Компонент</th>
                  <th>Ca</th>
                  <th>Ce</th>
                  <th>Instability</th>
                  <th>Coupling</th>
                  <th>Cohesion</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map((m) => {
                  const status = couplingLabel(m.coupling_score);
                  return (
                    <tr key={m.id}>
                      <td><strong>{m.component}</strong></td>
                      <td>{m.ca}</td>
                      <td>{m.ce}</td>
                      <td>{m.instability.toFixed(2)}</td>
                      <td>{m.coupling_score.toFixed(2)}</td>
                      <td>{m.cohesion_score.toFixed(2)}</td>
                      <td><span className={`pill ${status.cls}`}>{status.label}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="detail-grid">
        <article className="card">
          <h3>Hotspot-модули</h3>
          <p>Самые связанные компоненты — кандидаты на рефакторинг.</p>
          {hotspots.length === 0 ? (
            <p style={{ color: 'var(--muted)', marginTop: 12 }}>Нет данных.</p>
          ) : (
            <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
              {hotspots.map((m) => {
                const status = couplingLabel(m.coupling_score);
                return (
                  <div className="vuln-row" key={m.id}>
                    <strong>{m.component}</strong>
                    <small>Coupling {m.coupling_score.toFixed(2)} · Cohesion {m.cohesion_score.toFixed(2)}</small>
                    <span className={`pill ${status.cls}`}>{status.label}</span>
                  </div>
                );
              })}
            </div>
          )}
        </article>

        <article className="card">
          <h3>Рекомендации</h3>
          <p>Шаги по снижению архитектурного долга.</p>
          {recommendations.length === 0 ? (
            <p style={{ color: 'var(--muted)', marginTop: 12 }}>Метрики в норме — рекомендаций нет.</p>
          ) : (
            <div className="issue-list">
              {recommendations.map((rec) => (
                <div className="issue" key={rec.id}>
                  <div className="issue-top">
                    <strong>{rec.rule}{rec.component ? ` · ${rec.component}` : ''}</strong>
                    <span className={`pill ${SEVERITY_PILL[rec.severity] || 'pill-neutral'}`}>
                      {rec.severity}
                    </span>
                  </div>
                  <small>{rec.message}</small>
                </div>
              ))}
            </div>
          )}
        </article>
      </section>
    </div>
  );
}
