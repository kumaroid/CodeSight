import { useMemo } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { useProjectAnalysis } from '../hooks/useProjectAnalysis';
import { SAGA_STATUS, STEP_LABEL, formatDate, sagaProgress } from '../utils/status';
import { SEVERITY_PILL, severityRank, computeQualityScore } from '../utils/quality';
import CollapsibleSection from '../components/CollapsibleSection';

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
      archRecommendations,
      testingRun,
      dastRun,
    }),
    [codeIssues, findings, archSummary, archRecommendations, testingRun, dastRun],
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
  const avgCoupling =
    typeof archSummary?.avg_coupling === 'number'
      ? archSummary.avg_coupling
      : archMetrics.length > 0
        ? archMetrics.reduce((a, m) => a + m.coupling_score, 0) / archMetrics.length
        : undefined;
  const cohesionValues = archMetrics
    .map((m) => m.cohesion_score)
    .filter((v) => typeof v === 'number');
  const avgCohesion =
    typeof archSummary?.avg_cohesion === 'number'
      ? archSummary.avg_cohesion
      : cohesionValues.length > 0
        ? cohesionValues.reduce((a, v) => a + v, 0) / cohesionValues.length
        : undefined;

  const archHotspotStatus = (m) => {
    const c = m.coupling_score ?? 0;
    const i = typeof m.instability === 'number' ? m.instability : 0;
    if (c >= 0.7 || i > 0.7) return { label: 'Risk', cls: 'pill-error' };
    if (c >= 0.4 || i > 0.5) return { label: 'Review', cls: 'pill-warning' };
    return { label: 'Stable', cls: 'pill-success' };
  };

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Результаты анализа</div>
          <h1>{project?.name || `Проект ${id}`}</h1>
          <p className="description">
            Сводка по результатам анализа.
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

      {/* 1. Сводка качества: кольцо + KPI-плитки в одном ряду */}
      <section className="card report-summary">
        <div className="report-summary-score">
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
            <div className="legend-row">
              <div className="legend-left"><span className="dot dot-neutral" /><span>Динамика</span></div>
              <strong>{quality.breakdown.dynamic}</strong>
            </div>
          </div>
        </div>

        <div className="report-summary-kpis">
          <div className="section-header" style={{ marginBottom: 4 }}>
            <div>
              <h2 style={{ margin: 0 }}>Сводка качества</h2>
              <p style={{ margin: '4px 0 0' }}>Ключевые показатели по последнему запуску.</p>
            </div>
            <span className="pill pill-primary">Quality overview</span>
          </div>
          <div className="kpi-grid">
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
              <strong>Coupling (средн.)</strong>
              <span className="value">{typeof avgCoupling === 'number' ? avgCoupling.toFixed(2) : '—'}</span>
              <span className="meta">Средняя связность</span>
            </div>
            <div className="kpi">
              <strong>Cohesion (средн.)</strong>
              <span className="value">{typeof avgCohesion === 'number' ? avgCohesion.toFixed(2) : '—'}</span>
              <span className="meta">Среднее сцепление</span>
            </div>
            <div className="kpi">
              <strong>DAST findings</strong>
              <span className="value">{dastRun?.findings_total ?? '—'}</span>
              <span className="meta">
                {dastRun
                  ? `${dastRun.findings_errors ?? 0} errors · ${dastRun.findings_warnings ?? 0} warnings`
                  : 'Динамика не запускалась'}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Что чинить в первую очередь: топ-замечания + архитектурные hotspots */}
      <section className="detail-grid">
        <CollapsibleSection
          title="Критические замечания"
          subtitle="Первоочередные проблемы из всех модулей."
          badge={topIssues.length || undefined}
        >
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
            <p style={{ color: 'var(--muted)' }}>Серьёзных замечаний нет.</p>
          )}
        </CollapsibleSection>

        <CollapsibleSection
          title="Архитектурные hotspots"
          subtitle="Самые связанные компоненты проекта."
          badge={archMetrics.length || undefined}
          actions={
            <button
              type="button"
              className="btn btn-ghost"
              style={{ padding: '7px 12px' }}
              onClick={() => navigate(`/projects/${id}/architecture${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}
            >
              Открыть →
            </button>
          }
        >
          {archMetrics.length > 0 ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {[...archMetrics]
                .sort((a, b) => b.coupling_score - a.coupling_score)
                .slice(0, 5)
                .map((m) => {
                  const hs = archHotspotStatus(m);
                  return (
                    <div className="vuln-row" key={m.id}>
                      <strong>{m.component}</strong>
                      <small>
                        Coupling {m.coupling_score.toFixed(2)} · Cohesion {typeof m.cohesion_score === 'number' ? m.cohesion_score.toFixed(2) : '—'}
                        {typeof m.instability === 'number' ? ` · I ${m.instability.toFixed(2)}` : ''}
                      </small>
                      <span className={`pill ${hs.cls}`}>{hs.label}</span>
                    </div>
                  );
                })}
            </div>
          ) : (
            <p style={{ color: 'var(--muted)' }}>Архитектурные данные не получены (шаг arch не выполнен или нет графа модулей).</p>
          )}
        </CollapsibleSection>
      </section>

      {/* 3. Coverage по файлам + статус шагов саги */}
      <section className="detail-grid">
        <CollapsibleSection
          title="Покрытие тестами по модулям"
          subtitle="Файлы с самой низкой долей покрытия."
          badge={testingRun?.file_coverages?.length || undefined}
          actions={
            <button
              type="button"
              className="btn btn-ghost"
              style={{ padding: '7px 12px' }}
              onClick={() => navigate(`/projects/${id}/testing${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}
            >
              Все файлы →
            </button>
          }
        >
          {testingRun?.file_coverages?.length ? (
            <div style={{ display: 'grid', gap: 10 }}>
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
            <p style={{ color: 'var(--muted)' }}>Данные о покрытии не получены.</p>
          )}
        </CollapsibleSection>

        <CollapsibleSection
          title="Шаги Анализа"
          subtitle="Выполненныe модули."
          actions={
            <button
              type="button"
              className="btn btn-ghost"
              style={{ padding: '7px 12px' }}
              onClick={() => navigate(`/projects/${id}/status${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}
            >
              Подробнее →
            </button>
          }
        >
          <div style={{ display: 'grid', gap: 10 }}>
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
        </CollapsibleSection>
      </section>

      {/* 4. Статический анализ — подробный список */}
      <CollapsibleSection
        level="h2"
        title="Статический анализ"
        subtitle="Ruff, Bandit, mypy — краткая выборка."
        badge={codeIssues.length || undefined}
        defaultOpen={false}
        actions={
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(`/projects/${id}/static${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}
          >
            Все замечания →
          </button>
        }
      >
        {codeIssues.length === 0 ? (
          <p style={{ color: 'var(--muted)' }}>
            {results.analysis
              ? 'Замечаний нет или запуск ещё не завершён.'
              : 'Нет данных SAST для этой саги (шаг analysis).'}
          </p>
        ) : (
          <div className="issue-list">
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
      </CollapsibleSection>

      {/* 5. Динамический анализ — таблица probes */}
      <CollapsibleSection
        level="h2"
        title="Динамический анализ"
        subtitle="Probes: байткод, smoke-импорты, pytest collect (dev-mode), профиль ресурсов, deps, valgrind/memcheck."
        badge={dastRun?.findings_total ?? undefined}
        defaultOpen={false}
        actions={
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(`/projects/${id}/dast${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}
          >
            Открыть отчёт DAST →
          </button>
        }
      >
        {!dastRun ? (
          <p style={{ color: 'var(--muted)' }}>Нет прогона DAST для выбранной саги.</p>
        ) : (
          <div>
            <p style={{ marginTop: 0 }}>
              <strong>Статус:</strong> {dastRun.status} · <strong>Режим:</strong>{' '}
              {dastRun.mode || dastRun.command_summary || '—'}
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              <span className="pill pill-error">{dastRun.findings_errors ?? 0} errors</span>
              <span className="pill pill-warning">{dastRun.findings_warnings ?? 0} warnings</span>
              <span className="pill pill-primary">{dastRun.findings_total ?? 0} findings</span>
            </div>
            {Array.isArray(dastRun.probes) && dastRun.probes.length > 0 && (
              <div style={{ overflowX: 'auto', marginTop: 12 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Probe</th>
                      <th>Статус</th>
                      <th>Findings</th>
                      <th>Резюме</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dastRun.probes.map((p) => {
                      const cls =
                        p.status === 'ok'
                          ? 'pill-success'
                          : p.status === 'warning'
                            ? 'pill-warning'
                            : p.status === 'error' || p.status === 'timeout'
                              ? 'pill-error'
                              : 'pill-neutral';
                      return (
                        <tr key={p.name}>
                          <td><code>{p.name}</code></td>
                          <td><span className={`pill ${cls}`}>{p.status}</span></td>
                          <td>{(p.findings || []).length}</td>
                          <td style={{ maxWidth: 420 }}><small>{p.summary || '—'}</small></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {dastRun.error_message && (
              <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 10 }}>
                {dastRun.error_message}
              </p>
            )}
          </div>
        )}
      </CollapsibleSection>

      {/* 6. Навигация — компактный ряд кнопок */}
      <section className="card">
        <div className="section-header">
          <div>
            <h3>Перейти в раздел</h3>
            <p>Отдельные страницы каждого вида анализа.</p>
          </div>
        </div>
        <div className="report-nav">
          <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/static${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}>Статический анализ</button>
          <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/security${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}>Безопасность</button>
          <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/architecture${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}>Архитектура</button>
          <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/testing${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}>Тестирование</button>
          <button className="btn btn-secondary" onClick={() => navigate(`/projects/${id}/dast${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}>Динамический анализ</button>
          <button className="btn btn-ghost" onClick={() => navigate(`/projects/${id}/status${sagaIdParam ? `?saga=${sagaIdParam}` : ''}`)}>Статус запуска</button>
          <button className="btn btn-ghost" onClick={() => navigate(`/projects/${id}`)}>← К проекту</button>
        </div>
      </section>
    </div>
  );
}
