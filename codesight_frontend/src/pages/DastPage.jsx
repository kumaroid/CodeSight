import { useMemo, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { useProjectAnalysis } from '../hooks/useProjectAnalysis';
import { formatDate } from '../utils/status';

const PROBE_LABELS = {
  bytecode_compile: 'Компиляция в байткод',
  smoke_imports: 'Smoke-импорты',
  pytest_collect: 'pytest --collect-only',
  resource_profile: 'Профиль ресурсов',
  pip_check: 'Зависимости',
  valgrind_memcheck: 'Valgrind / memcheck',
};

const PROBE_HINTS = {
  bytecode_compile: 'python -m compileall — ловит синтаксис и SyntaxWarning без запуска кода.',
  smoke_imports: 'Импорт каждого топ-уровневого пакета в отдельном подпроцессе.',
  pytest_collect: '-X dev + warnings-as-errors. Считает тесты и ловит ResourceWarning.',
  resource_profile: 'Peak RSS / wall time / CPU при импорте всего проекта.',
  pip_check: 'Разбор requirements*.txt: количество, дубликаты, malformed.',
  valgrind_memcheck: 'Запускается только при наличии C-расширений (*.so / *.pyx / Extension(...)).',
};

const STATUS_PILL = {
  ok: 'pill-success',
  warning: 'pill-warning',
  error: 'pill-error',
  skipped: 'pill-neutral',
  timeout: 'pill-error',
};

const SEVERITY_PILL = {
  error: 'pill-error',
  warning: 'pill-warning',
  info: 'pill-primary',
};

const fmtMs = (ms) => {
  if (typeof ms !== 'number' || ms < 0) return '—';
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
};

const fmtKb = (kb) => {
  if (typeof kb !== 'number' || kb <= 0) return '—';
  if (kb < 1024) return `${kb} KiB`;
  return `${(kb / 1024).toFixed(1)} MiB`;
};

/** Возвращает короткий «hero»-показатель для probe — компактный для UI. */
const heroMetric = (probe) => {
  const m = probe?.metrics || {};
  switch (probe?.name) {
    case 'bytecode_compile':
      return m.files_failed > 0 ? `${m.files_failed} файлов сломаны` : 'Без ошибок';
    case 'smoke_imports':
      return `${m.imports_total - m.imports_failed}/${m.imports_total} ok`;
    case 'pytest_collect':
      return `${m.tests_collected ?? 0} тестов`;
    case 'resource_profile':
      return fmtKb(m.peak_rss_kb);
    case 'pip_check':
      return `${m.total_requirements ?? 0} req`;
    case 'valgrind_memcheck':
      return (m.c_extension_hits?.length || 0) > 0
        ? `${m.c_extension_hits.length} C-ext`
        : 'нет C-ext';
    default:
      return '';
  }
};

export default function DastPage() {
  const { id } = useParams();
  const location = useLocation();
  const sagaId = new URLSearchParams(location.search).get('saga');
  const { project, saga, results, loading } = useProjectAnalysis(id, { sagaId });
  const run = results.dast;

  const probes = run?.probes || [];
  const aggregate = run?.aggregate || null;
  const rawLog = run?.raw_log || run?.valgrind_report || '';
  const [showRaw, setShowRaw] = useState(false);

  const allFindings = useMemo(
    () => probes.flatMap((p) => (p.findings || []).map((f) => ({ ...f, probe: p.name }))),
    [probes],
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
          <div className="eyebrow">Динамический анализ (DAST)</div>
          <h1>{project?.name || `Проект ${id}`}</h1>
          <p className="description">
            Набор независимых probes по чёрному ящику: компиляция в байткод, smoke-импорты,
            pytest collect в dev-режиме, профиль ресурсов, разбор зависимостей и условный
            valgrind/memcheck (только при наличии C-расширений).
          </p>
        </div>
        <div className="hero-side">
          <div className="meta-box">
            <strong>Статус</strong>
            <span>{run?.status || '—'}</span>
          </div>
          <div className="meta-box">
            <strong>Режим</strong>
            <span>{run?.mode || run?.command_summary || '—'}</span>
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
            Нет прогона DAST для этой саги. Убедитесь, что в запуске был шаг «Динамика».
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
          <div className="section-header">
            <div>
              <h2>Probes</h2>
              <p>Каждая проверка — независима, ошибки одной не валят другие.</p>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span className="pill pill-error">
                {run.findings_errors ?? 0} errors
              </span>
              <span className="pill pill-warning">
                {run.findings_warnings ?? 0} warnings
              </span>
              <span className="pill pill-primary">
                {run.findings_total ?? allFindings.length} findings
              </span>
            </div>
          </div>

          {probes.length === 0 ? (
            <p style={{ color: 'var(--muted)', marginTop: 12 }}>
              Probes ещё не записаны.
            </p>
          ) : (
            <div style={{ overflowX: 'auto', marginTop: 12 }}>
              <table>
                <thead>
                  <tr>
                    <th>Probe</th>
                    <th>Статус</th>
                    <th>Время</th>
                    <th>Ключевая метрика</th>
                    <th>Findings</th>
                    <th>Резюме</th>
                  </tr>
                </thead>
                <tbody>
                  {probes.map((p) => (
                    <tr key={p.name}>
                      <td>
                        <strong>{PROBE_LABELS[p.name] || p.name}</strong>
                        <br />
                        <small style={{ color: 'var(--muted)' }}>{PROBE_HINTS[p.name] || ''}</small>
                      </td>
                      <td>
                        <span className={`pill ${STATUS_PILL[p.status] || 'pill-neutral'}`}>
                          {p.status}
                        </span>
                      </td>
                      <td>{fmtMs(p.duration_ms)}</td>
                      <td>{heroMetric(p)}</td>
                      <td>{(p.findings || []).length}</td>
                      <td style={{ maxWidth: 360 }}>
                        <small>{p.summary || '—'}</small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {allFindings.length > 0 && (
        <section className="card">
          <div className="section-header">
            <div>
              <h2>Findings</h2>
              <p>Объединённый список того, что нашли probes.</p>
            </div>
          </div>
          <div className="issue-list" style={{ marginTop: 12 }}>
            {allFindings.slice(0, 50).map((f, idx) => (
              <div className="issue" key={`${f.probe}-${idx}`}>
                <div className="issue-top">
                  <strong>
                    {f.rule}
                    {f.file ? ` · ${f.file}${f.line != null ? `:${f.line}` : ''}` : ''}
                  </strong>
                  <span className={`pill ${SEVERITY_PILL[f.severity] || 'pill-neutral'}`}>
                    {f.severity}
                  </span>
                </div>
                <small style={{ color: 'var(--muted)' }}>{PROBE_LABELS[f.probe] || f.probe}</small>
                <small>{f.message}</small>
              </div>
            ))}
            {allFindings.length > 50 && (
              <p style={{ color: 'var(--muted)', fontSize: 13 }}>
                Показаны первые 50 из {allFindings.length}.
              </p>
            )}
          </div>
        </section>
      )}

      {aggregate?.metrics && Object.keys(aggregate.metrics).length > 0 && (
        <section className="card">
          <h2>Метрики</h2>
          <div style={{ overflowX: 'auto', marginTop: 12 }}>
            <table>
              <thead>
                <tr>
                  <th>Probe.метрика</th>
                  <th>Значение</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(aggregate.metrics)
                  .filter(([, v]) => typeof v !== 'object' || v == null)
                  .map(([k, v]) => (
                    <tr key={k}>
                      <td><code>{k}</code></td>
                      <td>{v == null ? '—' : String(v)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {rawLog && (
        <section className="card">
          <div className="section-header">
            <div>
              <h2>Сырой лог</h2>
              <p>Полный stdout/stderr всех probes — для отладки.</p>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowRaw((s) => !s)}
            >
              {showRaw ? 'Скрыть' : 'Показать'}
            </button>
          </div>
          {showRaw && (
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
              {rawLog.length > 100000 ? `${rawLog.slice(0, 100000)}\n… [обрезано]` : rawLog}
            </pre>
          )}
        </section>
      )}

      {saga && (
        <p style={{ color: 'var(--muted)', fontSize: 13 }}>Saga: {saga.saga_id}</p>
      )}
    </div>
  );
}
