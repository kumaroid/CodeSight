import { useMemo } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { useProjectAnalysis } from '../hooks/useProjectAnalysis';
import { formatDate } from '../utils/status';

const OUTCOME_PILL = {
  passed: 'pill-success',
  failed: 'pill-error',
  error: 'pill-error',
  skipped: 'pill-warning',
  xfailed: 'pill-warning',
  xpassed: 'pill-primary',
};

const fmtPercent = (value) =>
  typeof value === 'number' ? `${value.toFixed(1)}%` : '—';

const fmtSeconds = (value) => {
  if (typeof value !== 'number' || value < 0) return '—';
  if (value < 1) return `${Math.round(value * 1000)} ms`;
  if (value < 60) return `${value.toFixed(1)} s`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value - minutes * 60);
  return `${minutes}m ${seconds}s`;
};

export default function TestingPage() {
  const { id } = useParams();
  const location = useLocation();
  const sagaId = new URLSearchParams(location.search).get('saga');
  const { project, saga, results, loading } = useProjectAnalysis(id, { sagaId });
  const run = results.testing;

  const fileCoverages = run?.file_coverages || [];
  const testResults = run?.test_results || [];

  const sortedCoverages = useMemo(
    () =>
      [...fileCoverages].sort(
        (a, b) => (a.coverage_percent ?? 0) - (b.coverage_percent ?? 0),
      ),
    [fileCoverages],
  );

  const failingTests = useMemo(
    () =>
      testResults.filter(
        (t) => t.outcome === 'failed' || t.outcome === 'error',
      ),
    [testResults],
  );

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
          <div className="eyebrow">Тесты и покрытие</div>
          <h1>{project?.name || `Проект ${id}`}</h1>
          <p className="description">
            pytest + coverage — результаты последнего запуска шага «Тесты».
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
            Нет данных тестирования для выбранной саги. Запустите полный анализ с
            шагом «Тесты» или откройте отчёт с параметром <code>?saga=…</code>{' '}
            в адресе.
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
              <h2>Сводка по тестам</h2>
              <p>Покрытие, количество тестов и время выполнения.</p>
            </div>
          </div>
          <div className="kpi-grid">
            <div className="kpi">
              <strong>Покрытие</strong>
              <span className="value">{fmtPercent(run.coverage_percent)}</span>
              <span className="meta">
                {typeof run.lines_covered === 'number' && typeof run.lines_total === 'number'
                  ? `${run.lines_covered}/${run.lines_total} строк`
                  : 'Данные о строках не получены'}
              </span>
            </div>
            <div className="kpi">
              <strong>Покрытие веток</strong>
              <span className="value">{fmtPercent(run.branch_coverage_percent)}</span>
              <span className="meta">
                {typeof run.branches_covered === 'number' && typeof run.branches_total === 'number'
                  ? `${run.branches_covered}/${run.branches_total} веток`
                  : 'Branch coverage не собирался'}
              </span>
            </div>
            <div className="kpi">
              <strong>Тесты</strong>
              <span className="value">{run.tests_total ?? 0}</span>
              <span className="meta">
                {(run.tests_passed ?? 0)} прошли · {(run.tests_failed ?? 0)} упали · {(run.tests_error ?? 0)} ошибок · {(run.tests_skipped ?? 0)} пропущено
              </span>
            </div>
            <div className="kpi">
              <strong>Длительность</strong>
              <span className="value">{fmtSeconds(run.duration_seconds)}</span>
              <span className="meta">Общее время прогона pytest</span>
            </div>
          </div>
        </section>
      )}

      {run && (
        <section className="card">
          <div className="section-header">
            <div>
              <h2>Покрытие по файлам ({fileCoverages.length})</h2>
              <p>Сортировка: от наименее покрытых к более покрытым.</p>
            </div>
          </div>
          {fileCoverages.length === 0 ? (
            <p style={{ color: 'var(--muted)', marginTop: 12 }}>
              Покрытие по файлам не получено.
            </p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Файл</th>
                    <th>Покрытие</th>
                    <th>Строки</th>
                    <th>Пропущено</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedCoverages.map((f) => (
                    <tr key={f.id}>
                      <td>
                        <small>{f.file_path}</small>
                      </td>
                      <td>
                        <span
                          className={`pill ${
                            f.coverage_percent < 60
                              ? 'pill-error'
                              : f.coverage_percent < 80
                                ? 'pill-warning'
                                : 'pill-success'
                          }`}
                        >
                          {fmtPercent(f.coverage_percent)}
                        </span>
                      </td>
                      <td>
                        <small>
                          {f.lines_covered}/{f.lines_total}
                        </small>
                      </td>
                      <td>
                        <small>{f.lines_missing}</small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {run && testResults.length > 0 && (
        <section className="card">
          <div className="section-header">
            <div>
              <h2>
                {failingTests.length > 0
                  ? `Упавшие тесты (${failingTests.length})`
                  : `Результаты тестов (${testResults.length})`}
              </h2>
              <p>
                {failingTests.length > 0
                  ? 'Показаны только тесты со статусом failed/error.'
                  : 'Все тесты прошли успешно.'}
              </p>
            </div>
          </div>
          {failingTests.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Тест</th>
                    <th>Статус</th>
                    <th>Длительность</th>
                    <th>Сообщение</th>
                  </tr>
                </thead>
                <tbody>
                  {failingTests.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <small>{t.node_id}</small>
                      </td>
                      <td>
                        <span className={`pill ${OUTCOME_PILL[t.outcome] || 'pill-neutral'}`}>
                          {t.outcome}
                        </span>
                      </td>
                      <td>
                        <small>{fmtSeconds(t.duration_seconds)}</small>
                      </td>
                      <td style={{ maxWidth: 480 }}>
                        <small style={{ whiteSpace: 'pre-wrap' }}>
                          {t.longrepr || '—'}
                        </small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
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
