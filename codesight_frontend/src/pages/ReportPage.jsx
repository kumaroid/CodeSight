import { useMemo } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { useProjectAnalysis } from '../hooks/useProjectAnalysis';
import { SAGA_STATUS, STEP_LABEL, formatDate, sagaProgress } from '../utils/status';

const SEVERITY_PILL = {
  critical: 'pill-error',
  high: 'pill-error',
  error: 'pill-error',
  medium: 'pill-warning',
  warning: 'pill-warning',
  low: 'pill-neutral',
  info: 'pill-primary',
};

const severityRank = { critical: 4, high: 3, error: 3, warning: 2, medium: 2, low: 1, info: 0 };

const countBySeverity = (items, getSev) => {
  const acc = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  items.forEach((item) => {
    const sev = (getSev(item) || '').toLowerCase();
    if (sev === 'error' || sev === 'high') acc.high += 1;
    else if (sev === 'critical') acc.critical += 1;
    else if (sev === 'medium' || sev === 'warning') acc.medium += 1;
    else if (sev === 'low') acc.low += 1;
    else acc.info += 1;
  });
  return acc;
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const computeQualityScore = ({ codeIssues, securityFindings, archSummary, testingRun }) => {
  let codeScore = 100;
  if (codeIssues) {
    const c = countBySeverity(codeIssues, (i) => i.severity);
    codeScore = clamp(100 - c.high * 6 - c.medium * 2 - c.low * 0.5, 0, 100);
  }
  let secScore = 100;
  if (securityFindings) {
    const c = countBySeverity(securityFindings, (i) => i.severity);
    secScore = clamp(100 - c.critical * 25 - c.high * 12 - c.medium * 4 - c.low, 0, 100);
  }
  const archScore = archSummary?.architecture_health_score ?? 100;
  const coverage = testingRun?.coverage_percent;
  const testScore = typeof coverage === 'number' ? clamp(coverage, 0, 100) : 100;

  const total = Math.round((codeScore + secScore + archScore + testScore) / 4);
  return {
    total,
    breakdown: {
      code: Math.round(codeScore),
      security: Math.round(secScore),
      architecture: Math.round(archScore),
      tests: Math.round(testScore),
    },
  };
};

export default function ReportPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const sagaIdParam = params.get('saga');

  const { project, saga, results, loading, error } = useProjectAnalysis(id, {
    sagaId: sagaIdParam,
  });

  const codeIssues = results.analysis?.issues || [];
  const findings = results.security?.findings || [];
  const archMetrics = results.arch?.metrics || [];
  const archSummary = results.arch?.summary || null;
  const archRecommendations = results.arch?.recommendations || [];
  const testingRun = results.testing || null;
  const dastRun = results.dast || null;

  const quality = useMemo(
    () => computeQualityScore({
      codeIssues,
      securityFindings: findings,
      archSummary,
      testingRun,
    }),
    [codeIssues, findings, archSummary, testingRun],
  );

  const topIssues = useMemo(() => {
    const all = [
      ...codeIssues.map((i) => ({
        title: `${i.tool}: ${i.code || ''} ${i.message}`.trim(),
        severity: i.severity,
        location: `${i.file_path}${i.line ? `:${i.line}` : ''}`,
        kind: 'code',
      })),
      ...findings.map((f) => ({
        title: `${f.owasp_category}: ${f.message}`,
        severity: f.severity,
        location: `${f.file_path}${f.line ? `:${f.line}` : ''}`,
        kind: 'security',
      })),
      ...archRecommendations.map((r) => ({
        title: `${r.rule}: ${r.message}`,
        severity: r.severity,
        location: r.component || 'architecture',
        kind: 'arch',
      })),
    ];
    return all
      .sort((a, b) => (severityRank[b.severity?.toLowerCase()] || 0) - (severityRank[a.severity?.toLowerCase()] || 0))
      .slice(0, 5);
  }, [codeIssues, findings, archRecommendations]);

  if (loading) {
    return (
      <div style={{ minHeight: '70vh', display: 'grid', placeItems: 'center', color: 'var(--muted)' }}>
        <div style={{ textAlign: 'center' }}>
          <RefreshCw size={32} style={{ margin: '0 auto 12px' }} />
          <p>Загрузка отчёта...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ background: 'var(--error-bg)', color: 'var(--error-text)' }}>
        {error}
      </div>
    );
  }

  const sagaMeta = saga
    ? SAGA_STATUS[saga.status] || { label: saga.status, cls: 'pill-neutral' }
    : null;
  const ringDeg = `calc(${quality.total}% * 3.6deg)`;

  const coverage = testingRun?.coverage_percent;
  const totalIssues = codeIssues.length + findings.length + archRecommendations.length;
  const totalSecurity = findings.length;
  const avgCoupling = archSummary?.avg_coupling;

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Результаты анализа</div>
          <h1>{project?.name || `Проект ${id}`}</h1>
          <p className="description">
            Сводка по статическому анализу, безопасности, архитектурной связности и тестам.
          </p>
        </div>
        <div className="hero-side">
          <div className="meta-box">
            <strong>Последний запуск</strong>
            <span>{formatDate(project?.updated_at)}</span>
          </div>
          <div className="meta-box">
            <strong>Saga</strong>
            <span>
              {sagaMeta ? (
                <span className={`pill ${sagaMeta.cls}`}>{sagaMeta.label}</span>
              ) : (
                <span className="pill pill-neutral">Нет запуска</span>
              )}
            </span>
          </div>
        </div>
      </section>

      {saga && saga.status !== 'completed' && (
        <div className="card" style={{ background: 'var(--surface-2)' }}>
          <p style={{ margin: 0 }}>
            Анализ ещё выполняется ({sagaProgress(saga)}%). Метрики будут обновляться автоматически.
          </p>
        </div>
      )}

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Ключевые показатели качества</h2>
            <p>Метрики собраны из всех сервисов анализа.</p>
          </div>
          <span className="pill pill-primary">Quality overview</span>
        </div>
        <div className="kpi-grid">
          <div className="kpi">
            <strong>Quality score</strong>
            <span className="value">{quality.total}</span>
            <span className="meta">Интегральная оценка качества по всем модулям.</span>
          </div>
          <div className="kpi">
            <strong>Coverage</strong>
            <span className="value">{typeof coverage === 'number' ? `${coverage.toFixed(1)}%` : '—'}</span>
            <span className="meta">
              {testingRun
                ? `${testingRun.tests_passed || 0}/${testingRun.tests_total || 0} тестов прошли`
                : 'Тесты не запускались'}
            </span>
          </div>
          <div className="kpi">
            <strong>Замечания</strong>
            <span className="value">{totalIssues}</span>
            <span className="meta">{codeIssues.length} статика · {totalSecurity} security · {archRecommendations.length} архитектура</span>
          </div>
          <div className="kpi">
            <strong>Security</strong>
            <span className="value">{totalSecurity}</span>
            <span className="meta">{findings.filter((f) => f.severity === 'critical' || f.severity === 'high').length} критичных</span>
          </div>
          <div className="kpi">
            <strong>Coupling</strong>
            <span className="value">{typeof avgCoupling === 'number' ? avgCoupling.toFixed(2) : '—'}</span>
            <span className="meta">Средняя связность между компонентами</span>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Статический анализ (SAST)</h2>
            <p>Ruff, Bandit, mypy — краткая выборка; полный список на отдельной странице.</p>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(`/projects/${id}/static${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}
          >
            Все замечания →
          </button>
        </div>
        {codeIssues.length === 0 ? (
          <p style={{ color: 'var(--muted)', marginTop: 12 }}>
            {results.analysis
              ? 'Замечаний нет или запуск ещё не завершён.'
              : 'Нет данных SAST для этой саги (шаг analysis).'}
          </p>
        ) : (
          <div className="issue-list" style={{ marginTop: 12 }}>
            {codeIssues.slice(0, 12).map((i) => (
              <div className="issue" key={i.id}>
                <div className="issue-top">
                  <strong>{i.tool}: {i.message}</strong>
                  <span className={`pill ${SEVERITY_PILL[i.severity?.toLowerCase()] || 'pill-neutral'}`}>{i.severity}</span>
                </div>
                <small>{i.file_path}{i.line != null ? `:${i.line}` : ''}</small>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Динамический анализ (DAST)</h2>
            <p>Valgrind + pytest collect / smoke. Подробный лог — на странице DAST.</p>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(`/projects/${id}/dast${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}
          >
            Открыть отчёт DAST →
          </button>
        </div>
        {!dastRun ? (
          <p style={{ color: 'var(--muted)', marginTop: 12 }}>Нет прогона DAST для выбранной саги.</p>
        ) : (
          <div style={{ marginTop: 12 }}>
            <p><strong>Статус:</strong> {dastRun.status} · <strong>Режим:</strong> {dastRun.command_summary || '—'}</p>
            {dastRun.error_message && (
              <p style={{ color: 'var(--muted)', fontSize: 13 }}>{dastRun.error_message}</p>
            )}
            {dastRun.valgrind_report && (
              <pre
                style={{
                  marginTop: 10,
                  padding: 12,
                  borderRadius: 10,
                  background: 'var(--surface-2)',
                  fontSize: 11,
                  maxHeight: 200,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {dastRun.valgrind_report.slice(0, 4000)}
                {dastRun.valgrind_report.length > 4000 ? '\n…' : ''}
              </pre>
            )}
          </div>
        )}
      </section>

      <section className="dashboard-grid">
        <div className="stack">
          <article className="card">
            <h3>Покрытие тестами по модулям</h3>
            <p>Файлы с самой низкой долей покрытия.</p>
            {testingRun?.file_coverages?.length ? (
              <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
                {[...testingRun.file_coverages]
                  .sort((a, b) => a.coverage_percent - b.coverage_percent)
                  .slice(0, 6)
                  .map((file) => (
                    <div className="vuln-row" key={file.id}>
                      <strong style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {file.file_path}
                      </strong>
                      <small>{file.lines_covered}/{file.lines_total} строк</small>
                      <span className={`pill ${file.coverage_percent < 60 ? 'pill-error' : 'pill-success'}`}>
                        {file.coverage_percent.toFixed(0)}%
                      </span>
                    </div>
                  ))}
              </div>
            ) : (
              <p style={{ color: 'var(--muted)', marginTop: 12 }}>Данные о покрытии не получены.</p>
            )}
          </article>

          <div className="detail-grid">
            <article className="card">
              <h3>Критические замечания</h3>
              <p>Первоочередные проблемы из всех модулей.</p>
              {topIssues.length > 0 ? (
                <div className="issue-list">
                  {topIssues.map((issue) => (
                    <div className="issue" key={`${issue.kind}-${issue.title}-${issue.location}`}>
                      <div className="issue-top">
                        <strong style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{issue.title}</strong>
                        <span className={`pill ${SEVERITY_PILL[issue.severity?.toLowerCase()] || 'pill-neutral'}`}>
                          {issue.severity}
                        </span>
                      </div>
                      <small>{issue.location}</small>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ color: 'var(--muted)', marginTop: 12 }}>Серьёзных замечаний нет.</p>
              )}
            </article>

            <article className="card">
              <h3>Архитектурная сводка</h3>
              <p>Самые связанные компоненты проекта.</p>
              {archMetrics.length > 0 ? (
                <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
                  {[...archMetrics]
                    .sort((a, b) => b.coupling_score - a.coupling_score)
                    .slice(0, 4)
                    .map((m) => (
                      <div className="vuln-row" key={m.id}>
                        <strong>{m.component}</strong>
                        <small>Coupling {m.coupling_score.toFixed(2)} · Cohesion {m.cohesion_score.toFixed(2)}</small>
                        <span className={`pill ${
                          m.coupling_score > 0.7 ? 'pill-error' : m.coupling_score > 0.4 ? 'pill-warning' : 'pill-success'
                        }`}>
                          {m.coupling_score > 0.7 ? 'Risk' : m.coupling_score > 0.4 ? 'Review' : 'Stable'}
                        </span>
                      </div>
                    ))}
                </div>
              ) : (
                <p style={{ color: 'var(--muted)', marginTop: 12 }}>Архитектурные данные не получены (шаг arch не выполнен или нет графа модулей).</p>
              )}
            </article>
          </div>
        </div>

        <aside className="stack">
          <article className="card" style={{ textAlign: 'center' }}>
            <h3>Интегральная оценка</h3>
            <p>Сводный score и разложение по направлениям.</p>
            <div className="score-ring" style={{ background: `conic-gradient(var(--primary) ${ringDeg}, rgba(36,34,30,0.08) 0)` }}>
              <div className="score-content">
                <span className="big">{quality.total}</span>
                <span className="sub">из 100</span>
              </div>
            </div>
            <div className="legend">
              <div className="legend-row">
                <div className="legend-left"><span className="dot dot-primary" /><span>Код</span></div>
                <strong>{quality.breakdown.code}</strong>
              </div>
              <div className="legend-row">
                <div className="legend-left"><span className="dot dot-success" /><span>Тесты</span></div>
                <strong>{quality.breakdown.tests}</strong>
              </div>
              <div className="legend-row">
                <div className="legend-left"><span className="dot dot-warning" /><span>Безопасность</span></div>
                <strong>{quality.breakdown.security}</strong>
              </div>
              <div className="legend-row">
                <div className="legend-left"><span className="dot dot-error" /><span>Архитектура</span></div>
                <strong>{quality.breakdown.architecture}</strong>
              </div>
            </div>
          </article>

          <article className="card">
            <h3>Шаги анализа</h3>
            <p>Состояние выполненных модулей.</p>
            <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
              {saga
                ? Object.entries(saga.steps_status).map(([step, status]) => (
                    <div className="vuln-row" key={step}>
                      <strong>{STEP_LABEL[step]?.label || step}</strong>
                      <small>{STEP_LABEL[step]?.desc || ''}</small>
                      <span className={`pill ${
                        status === 'completed' ? 'pill-success' : status === 'failed' ? 'pill-error' : 'pill-running'
                      }`}>
                        {status}
                      </span>
                    </div>
                  ))
                : <p style={{ color: 'var(--muted)' }}>Запуск анализа не найден.</p>}
            </div>
          </article>

          <article className="card">
            <h3>Навигация</h3>
            <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
              <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/security`)}>Security анализ</button>
              <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/architecture`)}>Архитектура</button>
              <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/static${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}>Статический анализ</button>
              <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/dast${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}>DAST</button>
              <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/status`)}>Статус запуска</button>
              <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}`)}>К проекту</button>
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}
