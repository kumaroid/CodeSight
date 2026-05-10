import { useParams } from 'react-router-dom';

export default function ArchPage() {
  const { id } = useParams();

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="eyebrow">Архитектурный анализ</div>
          <h1>Связность и hotspot-модули проекта #{id || 1843}</h1>
          <p className="description">Экран фокусируется на графе зависимостей и модулях, которые сильнее всего влияют на архитектурную устойчивость проекта.</p>
        </div>
        <div className="hero-side">
          <div className="meta-box"><strong>Средний coupling</strong><span>0.68</span></div>
          <div className="meta-box"><strong>Hotspot-модулей</strong><span>3</span></div>
        </div>
      </section>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Граф зависимостей</h2>
            <p>Визуализация связей между ключевыми пакетами и сервисами.</p>
          </div>
          <span className="pill pill-primary">Dependency view</span>
        </div>
        <div className="arch-graph">
          <svg viewBox="0 0 800 320" width="100%" height="100%" aria-label="architecture graph">
            <defs>
              <linearGradient id="line" x1="0" x2="1">
                <stop offset="0%" stopColor="#0b6b6f" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#0b6b6f" stopOpacity="0.15" />
              </linearGradient>
            </defs>
            <g stroke="url(#line)" strokeWidth="2" fill="none">
              <path d="M160 80 C260 80, 280 160, 400 160" />
              <path d="M160 240 C260 240, 280 160, 400 160" />
              <path d="M400 160 C520 160, 540 100, 640 100" />
              <path d="M400 160 C520 160, 540 220, 640 220" />
            </g>
            {[
              { x: 110, y: 80, label: 'api/auth', risk: true },
              { x: 110, y: 240, label: 'api/files' },
              { x: 400, y: 160, label: 'services/users', risk: true },
              { x: 690, y: 100, label: 'repositories/base' },
              { x: 690, y: 220, label: 'integrations/ceph', risk: true },
            ].map((node) => (
              <g key={node.label} transform={`translate(${node.x}, ${node.y})`}>
                <circle r="28" fill={node.risk ? 'rgba(161,53,68,0.14)' : 'rgba(11,107,111,0.10)'} stroke={node.risk ? '#8d2e3a' : '#0b6b6f'} strokeWidth="2" />
                <text y="48" textAnchor="middle" fontSize="12" fill="#726e65">{node.label}</text>
              </g>
            ))}
          </svg>
        </div>
      </section>

      <section className="detail-grid">
        <article className="card">
          <h3>Hotspot-модули</h3>
          <p>Компоненты с повышенной входящей и исходящей связностью.</p>
          <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
            <div className="vuln-row"><strong>api/auth</strong><small>Coupling 0.74 · Cohesion 0.41</small><span className="pill pill-error">Risk</span></div>
            <div className="vuln-row"><strong>services/users</strong><small>Coupling 0.63 · Cohesion 0.52</small><span className="pill pill-warning">Review</span></div>
            <div className="vuln-row"><strong>integrations/ceph</strong><small>Coupling 0.66 · Cohesion 0.38</small><span className="pill pill-error">Risk</span></div>
          </div>
        </article>

        <article className="card">
          <h3>Рекомендованные действия</h3>
          <p>Шаги по снижению архитектурного долга.</p>
          <div className="issue-list">
            <div className="issue"><div className="issue-top"><strong>Выделить auth orchestration в отдельный сервисный слой</strong><span className="pill pill-error">High</span></div><small>Снизит прямые связи между API и репозиториями.</small></div>
            <div className="issue"><div className="issue-top"><strong>Сократить зависимость services/users от integrations</strong><span className="pill pill-warning">Medium</span></div><small>Добавить adapter-слой и интерфейсы.</small></div>
            <div className="issue"><div className="issue-top"><strong>Разделить файловую интеграцию на provider + gateway</strong><span className="pill pill-warning">Medium</span></div><small>Упростит тестирование и поддержку.</small></div>
          </div>
        </article>
      </section>
    </div>
  );
}
