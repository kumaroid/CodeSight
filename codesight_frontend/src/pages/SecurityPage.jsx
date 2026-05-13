import { useMemo } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { useProjectAnalysis } from '../hooks/useProjectAnalysis';

const SEVERITY_PILL = {
  critical: 'pill-error',
  high: 'pill-error',
  medium: 'pill-warning',
  low: 'pill-neutral',
  info: 'pill-primary',
};

const SEVERITY_RANK = { critical: 4, high: 3, medium: 2, low: 1, info: 0 };

export default function SecurityPage() {
  const { id } = useParams();
  const location = useLocation();
  const sagaId = new URLSearchParams(location.search).get('saga');
  const { project, results, loading } = useProjectAnalysis(id, { sagaId });
  const scan = results.security;
  const findings = scan?.findings || [];

  const stats = useMemo(() => {
    const acc = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    findings.forEach((f) => {
      const sev = (f.severity || '').toLowerCase();
      if (sev in acc) acc[sev] += 1;
    });
    return acc;
  }, [findings]);

  const grouped = useMemo(() => {
    const map = new Map();
    findings.forEach((f) => {
      const key = `${f.owasp_category} ${f.owasp_title}`;
      if (!map.has(key)) {
        map.set(key, {
          category: f.owasp_category,
          title: f.owasp_title,
          items: [],
        });
      }
      map.get(key).items.push(f);
    });
    return Array.from(map.values()).sort((a, b) => a.category.localeCompare(b.category));
  }, [findings]);

  const topFindings = useMemo(
    () =>
      [...findings].sort(
        (a, b) =>
          (SEVERITY_RANK[b.severity?.toLowerCase()] || 0) -
          (SEVERITY_RANK[a.severity?.toLowerCase()] || 0),
      ),
    [findings],
  );

  if (loading) {
    return (
      <div style={{ minHeight: '70vh', display: 'grid', placeItems: 'center', color: 'var(--muted)' }}>
        <div style={{ textAlign: 'center' }}>
          <RefreshCw size={32} style={{ margin: '0 auto 12px' }} />
          <p>Загружаем отчёт по безопасности...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Security анализ</div>
          <h1>{project?.name || `Проект ${id}`}</h1>
          <p className="description">
            Отчёт объединяет Bandit, regex-эвристики и pip-audit. Находки сгруппированы по OWASP Top 10.
          </p>
        </div>
        <div className="hero-side">
          <div className="meta-box">
            <strong>OWASP категорий</strong>
            <span>{grouped.length}</span>
          </div>
          <div className="meta-box">
            <strong>Findings</strong>
            <span>{findings.length}</span>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Сводка по уязвимостям</h2>
            <p>Распределение по серьёзности</p>
          </div>
          <span className={`pill ${findings.length > 0 ? 'pill-error' : 'pill-success'}`}>
            {findings.length} findings
          </span>
        </div>
        <div className="kpi-grid">
          <div className="kpi"><strong>Critical</strong><span className="value">{stats.critical}</span><span className="meta">Требуют немедленного исправления</span></div>
          <div className="kpi"><strong>High</strong><span className="value">{stats.high}</span><span className="meta">Повышенный риск</span></div>
          <div className="kpi"><strong>Medium</strong><span className="value">{stats.medium}</span><span className="meta">В ближайший спринт</span></div>
          <div className="kpi"><strong>Low / Info</strong><span className="value">{stats.low + stats.info}</span><span className="meta">Менее критичные сигналы</span></div>
        </div>
      </section>

      <section className="card">
        <h3>Все находки</h3>
        <p>Каждая запись содержит severity, OWASP-категорию и местоположение.</p>
        {topFindings.length === 0 ? (
          <p style={{ color: 'var(--muted)', marginTop: 14 }}>Уязвимости не найдены. Отлично!</p>
        ) : (
          <div className="vuln-table">
            {topFindings.map((item) => (
              <div className="vuln-row" key={item.id}>
                <div style={{
                  width: 12, height: 12, borderRadius: 999,
                  background:
                    item.severity === 'critical' || item.severity === 'high'
                      ? 'var(--error-text)'
                      : item.severity === 'medium'
                        ? 'var(--warning-text)'
                        : 'var(--primary)',
                }} />
                <div>
                  <strong>{item.checker.toUpperCase()} · {item.message}</strong>
                  <small>{item.file_path}{item.line ? `:${item.line}` : ''} · {item.owasp_category} {item.cwe ? `· ${item.cwe}` : ''}</small>
                </div>
                <span className={`pill ${SEVERITY_PILL[item.severity?.toLowerCase()] || 'pill-neutral'}`}>
                  {item.severity}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="detail-grid">
        <article className="card">
          <h3>OWASP Top 10</h3>
          <p>Соответствие типовым категориям угроз.</p>
          {grouped.length === 0 ? (
            <p style={{ color: 'var(--muted)', marginTop: 12 }}>Нет данных.</p>
          ) : (
            <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
              {grouped.map((group) => {
                const top = group.items.reduce((acc, item) =>
                  (SEVERITY_RANK[item.severity?.toLowerCase()] || 0) > (SEVERITY_RANK[acc.severity?.toLowerCase()] || 0)
                    ? item
                    : acc, group.items[0]);
                return (
                  <div className="vuln-row" key={group.category}>
                    <strong>{group.category} {group.title}</strong>
                    <small>{group.items.length} находок</small>
                    <span className={`pill ${SEVERITY_PILL[top.severity?.toLowerCase()] || 'pill-neutral'}`}>
                      {top.severity}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </article>

        <article className="card">
          <h3>Что исправить</h3>
          <p>Топ-3 критичных находки.</p>
          {topFindings.slice(0, 3).length === 0 ? (
            <p style={{ color: 'var(--muted)', marginTop: 12 }}>Список рекомендаций пуст.</p>
          ) : (
            <div className="issue-list">
              {topFindings.slice(0, 3).map((item) => (
                <div className="issue" key={item.id}>
                  <div className="issue-top">
                    <strong>{item.message}</strong>
                    <span className={`pill ${SEVERITY_PILL[item.severity?.toLowerCase()] || 'pill-neutral'}`}>
                      {item.severity}
                    </span>
                  </div>
                  <small>{item.file_path}{item.line ? `:${item.line}` : ''} · {item.owasp_category}</small>
                </div>
              ))}
            </div>
          )}
        </article>
      </section>
    </div>
  );
}
