import { useParams } from 'react-router-dom';

const vulnerabilities = [
  { title: 'urllib3 outdated dependency', path: 'requirements.txt', severity: 'Critical', cls: 'pill-error' },
  { title: 'Potential command injection', path: 'scripts/deploy.py:84', severity: 'High', cls: 'pill-error' },
  { title: 'Hardcoded temporary secret', path: 'settings/dev.py:17', severity: 'Medium', cls: 'pill-warning' },
  { title: 'Weak validation in upload endpoint', path: 'api/files.py:51', severity: 'Medium', cls: 'pill-warning' },
];

export default function SecurityPage() {
  const { id } = useParams();

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Security анализ</div>
          <h1>Отчёт по безопасности проекта #{id || 1843}</h1>
          <p className="description">Экран объединяет сигналы Bandit и Semgrep и группирует находки по severity и стандартам OWASP / CWE.</p>
        </div>
        <div className="hero-side">
          <div className="meta-box"><strong>OWASP Top 10</strong><span>4 совпадения</span></div>
          <div className="meta-box"><strong>CWE Top 25</strong><span>2 критичных риска</span></div>
        </div>
      </section>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Сводка по уязвимостям</h2>
            <p>Наиболее важные security-сигналы по проекту.</p>
          </div>
          <span className="pill pill-error">5 findings</span>
        </div>
        <div className="kpi-grid">
          <div className="kpi"><strong>Critical</strong><span className="value">2</span><span className="meta">Требуют немедленного исправления.</span></div>
          <div className="kpi"><strong>High</strong><span className="value">1</span><span className="meta">Повышенный риск эксплуатации.</span></div>
          <div className="kpi"><strong>Medium</strong><span className="value">2</span><span className="meta">Нужно включить в ближайший спринт.</span></div>
          <div className="kpi"><strong>ASVS coverage</strong><span className="value">82%</span><span className="meta">Часть требований уже покрыта.</span></div>
        </div>
      </section>

      <section className="card">
        <h3>Найденные проблемы</h3>
        <p>Каждая запись содержит severity и указание на место, где обнаружен риск.</p>
        <div className="vuln-table">
          {vulnerabilities.map((item) => (
            <div className="vuln-row" key={item.title}>
              <div style={{ width: 12, height: 12, borderRadius: 999, background: item.cls === 'pill-error' ? 'var(--error-text)' : 'var(--warning-text)' }} />
              <div>
                <strong>{item.title}</strong>
                <small>{item.path}</small>
              </div>
              <span className={`pill ${item.cls}`}>{item.severity}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="detail-grid">
        <article className="card">
          <h3>OWASP Top 10</h3>
          <p>Соответствие типовым категориям угроз.</p>
          <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
            <div className="vuln-row"><strong>A06 Vulnerable Components</strong><small>Найдены устаревшие зависимости</small><span className="pill pill-error">Critical</span></div>
            <div className="vuln-row"><strong>A03 Injection</strong><small>Опасный shell-вызов в deploy script</small><span className="pill pill-error">High</span></div>
            <div className="vuln-row"><strong>A05 Security Misconfiguration</strong><small>Слабая валидация upload endpoint</small><span className="pill pill-warning">Medium</span></div>
          </div>
        </article>

        <article className="card">
          <h3>Рекомендации</h3>
          <p>Что исправить в первую очередь.</p>
          <div className="issue-list">
            <div className="issue"><div className="issue-top"><strong>Обновить urllib3 до безопасной версии</strong><span className="pill pill-error">P1</span></div><small>Устранит критичную проблему с зависимостями.</small></div>
            <div className="issue"><div className="issue-top"><strong>Заменить shell=True на безопасный вызов</strong><span className="pill pill-error">P1</span></div><small>Снизит риск command injection.</small></div>
            <div className="issue"><div className="issue-top"><strong>Усилить валидацию загружаемых файлов</strong><span className="pill pill-warning">P2</span></div><small>Снизит риск обхода ограничений upload-механизма.</small></div>
          </div>
        </article>
      </section>
    </div>
  );
}
